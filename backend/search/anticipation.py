"""The "one step ahead" loop: a silent-by-default decision policy.

Every hub tick, for the results currently on screen, choose one action:

    silent            -- the overwhelmingly common output
    ack               -- evidence is building; show a small "watching" note
    propose_relayout  -- offer (never force) the same facts in another layout

Three response modes (after AURA's real-time / proactive / multi-response QA):
  * Reactive   -- at submit, the layout already fits the current state (server).
  * Deferred   -- after render, act once only when evidence is *sustained*: the
                  committed state differs from the rendered layout for SUSTAIN_S,
                  or struggle signals on this search reach STRUGGLE_THRESHOLD.
  * Continuous -- after an accepted change, further offers are allowed on the
                  same search, rate-limited by PROPOSAL_GAP_S.

Guards: nothing in the first READ_GRACE_S after render; nothing while Aura's
breathing guide is open; nothing after the user picked Standard view or undid
a change (they took control); a dismissed target is never offered again for
that search and all offers pause DISMISS_SUPPRESS_S (18 s, as in the webcam
app's copilot); an unanswered offer expires after PROPOSAL_TTL_S.

In Control (A) the same decisions are computed but only logged as
`counterfactual`, so false- and missed-intervention rates can be compared
across conditions. Every non-silent decision is logged.
"""
import itertools
import threading
import time

READ_GRACE_S = 2.0
SUSTAIN_S = 4.0
STRUGGLE_THRESHOLD = 2
PROPOSAL_GAP_S = 45.0          # min gap before a follow-up offer (continuous mode)
DISMISS_SUPPRESS_S = 18.0
PROPOSAL_TTL_S = 45.0
MAX_LOG = 500

OFFER_TEXT = {
    'overwhelmed': 'Simplify this to one clear answer and a next step?',
    'fatigued': 'Switch to a shorter, easier-to-read version?',
    'disoriented': 'Show where you are and help narrow it down?',
    'focused': 'Show the full detail and sources side by side?',
    'energized': 'Open the compare-and-explore view?',
}
_ids = itertools.count(1)


class Anticipator:
    def __init__(self):
        self._lock = threading.Lock()
        self.view = None            # the results currently on screen
        self.proposal = None
        self.ack = None
        self.log = []
        self.listener = None        # e.g. ResearchBridge.record_anticipation

    # ------------------------------------------------------------- views --
    def set_view(self, search_id, policy, reformulation=False, now=None):
        now = now if now is not None else time.time()
        with self._lock:
            if self.proposal:
                self._log(now, 'superseded', self.proposal['target'], 'new search')
            self.view = {'search_id': search_id, 'policy': policy, 'rendered_at': now,
                         'reformulation': bool(reformulation), 'override': False,
                         'dismissed': set(), 'suppress_until': 0.0, 'last_offer': 0.0,
                         'offers': 0, 'accepted': [], 'counterfactual_logged': set()}
            self.proposal, self.ack = None, None

    def user_choice(self, search_id, policy, now=None):
        """User switched layout themselves (Standard view / back to adapted)."""
        now = now if now is not None else time.time()
        with self._lock:
            v = self.view
            if not v or v['search_id'] != search_id:
                return
            v['override'] = policy == 'neutral'
            v['policy'] = policy
            if self.proposal:
                self._log(now, 'superseded', self.proposal['target'], 'user changed layout')
            self.proposal = None

    # ----------------------------------------------------------- decide --
    def decide(self, fused, adaptive, behaviour_since_render, dense, now=None):
        now = now if now is not None else time.time()
        with self._lock:
            self.ack = None
            v = self.view
            if not v or not fused:
                return self._snapshot()
            if self.proposal:
                if now - self.proposal['created_at'] > PROPOSAL_TTL_S:
                    self._log(now, 'expired', self.proposal['target'], 'no answer')
                    v['dismissed'].add(self.proposal['target'])
                    self.proposal = None
                return self._snapshot()
            if now - v['rendered_at'] < READ_GRACE_S:
                return self._snapshot()

            target, reason, partial = self._candidate(v, fused, behaviour_since_render, dense, now)

            if not adaptive:
                if target and target not in v['counterfactual_logged']:
                    v['counterfactual_logged'].add(target)
                    self._log(now, 'counterfactual', target, reason)
                return self._snapshot()
            if fused.get('quiet') or v['override'] or now < v['suppress_until']:
                return self._snapshot()

            allowed_offers = 1 + len(v['accepted'])
            if (target and target not in v['dismissed'] and v['offers'] < allowed_offers
                    and now - v['last_offer'] >= (PROPOSAL_GAP_S if v['offers'] else 0)):
                self.proposal = {'id': 'p{}'.format(next(_ids)), 'search_id': v['search_id'],
                                 'from': v['policy'], 'target': target, 'reason': reason,
                                 'text': OFFER_TEXT.get(target, 'Change the layout?'),
                                 'created_at': now}
                v['offers'] += 1
                v['last_offer'] = now
                self._log(now, 'proposal', target, reason)
            elif partial:
                self.ack = {'text': "I'll offer a simpler view if this gets heavy."}
            return self._snapshot()

    def _candidate(self, v, fused, beh, dense, now):
        rendered = v['policy']
        committed = fused.get('committed_state')
        # (a) the user's state moved away from the layout on screen, and stayed there
        if committed and committed != rendered and rendered != 'neutral':
            if dense.sustained('committed', committed, SUSTAIN_S, now):
                return committed, 'Your state changed to {} and stayed there.'.format(committed), False
            drift_pending = True
        else:
            drift_pending = False
        # (b) struggle on this very search
        struggle = (2 * int(v['reformulation']) + beh.get('backtracks', 0)
                    + beh.get('rage_clicks', 0) + beh.get('hesitations', 0))
        if struggle >= STRUGGLE_THRESHOLD:
            stress = fused.get('stress') or 0
            target = 'overwhelmed' if stress >= 45 else 'disoriented'
            if target != rendered:
                why = []
                if v['reformulation']:
                    why.append('you reworded the search')
                for k, label in (('backtracks', 'came straight back from a source'),
                                 ('rage_clicks', 'clicked repeatedly'),
                                 ('hesitations', 'paused a long time before clicking')):
                    if beh.get(k):
                        why.append(label)
                return target, 'It looks like this is hard going: ' + ', '.join(why) + '.', False
        partial = drift_pending or struggle == STRUGGLE_THRESHOLD - 1 or bool(fused.get('candidate_state'))
        return None, '', partial

    # ---------------------------------------------------------- respond --
    def respond(self, proposal_id, action, now=None):
        """accept -> returns the policy to show; dismiss -> None; undo -> previous policy."""
        now = now if now is not None else time.time()
        with self._lock:
            v = self.view
            if not v:
                raise KeyError('no active results')
            if action == 'undo':
                if not v['accepted']:
                    raise KeyError('nothing to undo')
                prev, target = v['accepted'].pop()
                self._log(now, 'undo', target, 'back to {}'.format(prev), from_=v['policy'])
                v['policy'], v['override'] = prev, True      # user took control: stop offering
                return prev
            p = self.proposal
            if not p or p['id'] != proposal_id:
                raise KeyError('no such proposal')
            self.proposal = None
            latency = round(now - p['created_at'], 1)
            if action == 'accept':
                self._log(now, 'accept', p['target'], p['reason'], from_=p['from'], latency_s=latency)
                v['accepted'].append((v['policy'], p['target']))
                v['policy'] = p['target']
                v['rendered_at'] = now
                return p['target']
            self._log(now, 'dismiss', p['target'], p['reason'], from_=p['from'], latency_s=latency)
            v['dismissed'].add(p['target'])
            v['suppress_until'] = now + DISMISS_SUPPRESS_S
            return None

    # ------------------------------------------------------------ utils --
    def _log(self, t, kind, target, reason, from_=None, **extra):
        """`from` is the layout on screen when the decision was made."""
        entry = dict({'t': round(t, 2), 'kind': kind, 'target': target, 'reason': reason,
                      'search_id': (self.view or {}).get('search_id'),
                      'from': from_ or (self.view or {}).get('policy')}, **extra)
        self.log.append(entry)
        del self.log[:-MAX_LOG]
        if self.listener:
            try:
                self.listener(entry)
            except Exception as e:      # recording must never break the search
                print('[Aura Search] anticipation listener failed:', e)

    def _snapshot(self):
        v = self.view
        return {'proposal': dict(self.proposal) if self.proposal else None,
                'ack': self.ack,
                'can_undo': bool(v and v['accepted']),
                'view': {'search_id': v['search_id'], 'policy': v['policy']} if v else None}

    def snapshot(self):
        with self._lock:
            return self._snapshot()

    def recent_log(self, n=50):
        with self._lock:
            return list(self.log[-n:])
