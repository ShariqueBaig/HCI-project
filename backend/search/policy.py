"""State -> AdaptationPolicy: the guardrails the GenUI composer must stay inside.

Deterministic and explainable. The LLM (Phase 3) may choose *within* a policy
-- which allowed widgets, how to condense -- but never outside it: the
validator truncates anything past `max_primary_options`, strips widgets not in
`allowed_widgets`, and drops the custom HTML slot unless `allow_custom_widget`.

Typography and target scales are seeded from the webcam app's
VISUAL_NAV_TAXONOMY (HCI Mood assignment/backend/emotional_agent.py) so the
Fitts's-law / readability adaptations carry over; colours stay Aura's.
`neutral` is the prompt-only policy used for Control (A) and Standard view.
"""
import copy

ALL_WIDGETS = ('AnswerCard', 'KeyFactsList', 'GuidedSteps', 'ComparisonTable', 'ProsCons',
               'Timeline', 'SourceList', 'FacetChips', 'FollowUpChips', 'ClarifierChips',
               'QueryTrail', 'BreathingNudge', 'ReadAloud')

_BASE = {
    'answer_word_budget': 120,
    'reading_level': 'general',
    'max_primary_options': 5,
    'max_key_facts': 8,
    'required_widgets': ['AnswerCard', 'SourceList'],
    'density': 'regular',
    'tone': 'neutral, informative',
    'show_facets': False,
    'show_sources_inline': True,
    'proactive': {'clarifiers': False, 'followups': True, 'breathing_nudge': False},
    'allow_custom_widget': False,
    'topology': 'stack',          # stack | split (main + side column) | stepper
    'tokens': {'targetScale': 1.0, 'typographyScale': 1.0, 'lineHeight': 1.55, 'accent': 'calm'},
}

_POLICIES = {
    'neutral': {
        'label': 'Standard',
        'summary': 'Same layout for everyone: answer, key facts, sources.',
        'allowed_widgets': ['AnswerCard', 'KeyFactsList', 'GuidedSteps', 'ComparisonTable',
                            'SourceList', 'FollowUpChips'],
    },
    'focused': {
        'label': 'Focused',
        'summary': 'Dense and complete: answer, comparison where useful, sources inline.',
        'answer_word_budget': 140,
        'max_primary_options': 6,
        'max_key_facts': 10,
        'required_widgets': ['AnswerCard', 'KeyFactsList', 'SourceList'],
        'density': 'dense',
        'tone': 'analytical and concise',
        'topology': 'split',
        'allowed_widgets': ['AnswerCard', 'KeyFactsList', 'GuidedSteps', 'ComparisonTable',
                            'ProsCons', 'Timeline', 'SourceList', 'FollowUpChips'],
    },
    'overwhelmed': {
        'label': 'Overwhelmed',
        'summary': 'One clear answer and the next step only; fewer choices, bigger targets.',
        'answer_word_budget': 45,
        'reading_level': 'plain',
        'max_primary_options': 1,
        'max_key_facts': 3,
        'required_widgets': ['AnswerCard', 'GuidedSteps', 'SourceList'],
        'density': 'sparse',
        'tone': 'calm, reassuring, one clear recommendation',
        'topology': 'stepper',
        'show_sources_inline': False,
        'allowed_widgets': ['AnswerCard', 'GuidedSteps', 'KeyFactsList', 'SourceList', 'BreathingNudge'],
        'proactive': {'clarifiers': False, 'followups': False, 'breathing_nudge': True},
        'tokens': {'targetScale': 1.26, 'typographyScale': 1.1, 'lineHeight': 1.72, 'accent': 'calm'},
    },
    'fatigued': {
        'label': 'Fatigued',
        'summary': 'Short and easy to read, with read-aloud; low effort to scan.',
        'answer_word_budget': 80,
        'reading_level': 'plain',
        'max_primary_options': 3,
        'max_key_facts': 4,
        'required_widgets': ['AnswerCard', 'ReadAloud', 'KeyFactsList', 'SourceList'],
        'density': 'sparse',
        'tone': 'warm, low effort',
        'allowed_widgets': ['AnswerCard', 'KeyFactsList', 'GuidedSteps', 'SourceList', 'ReadAloud'],
        'tokens': {'targetScale': 1.16, 'typographyScale': 1.14, 'lineHeight': 1.82, 'accent': 'calm'},
    },
    'energized': {
        'label': 'Energized',
        'summary': 'Explore and compare: comparison table, facets, follow-up paths.',
        'answer_word_budget': 120,
        'max_primary_options': 8,
        'max_key_facts': 10,
        'density': 'dense',
        'tone': 'exploratory and comparative',
        'show_facets': True,
        'topology': 'split',
        'allowed_widgets': list(ALL_WIDGETS[:10]),
        'allow_custom_widget': True,
        'tokens': {'targetScale': 1.04, 'typographyScale': 1.02, 'lineHeight': 1.6, 'accent': 'calm'},
    },
    'disoriented': {
        'label': 'Disoriented',
        'summary': 'Re-anchor: where you are, what you searched, top 3 options, step by step.',
        'answer_word_budget': 90,
        'max_primary_options': 3,
        'max_key_facts': 5,
        'required_widgets': ['QueryTrail', 'AnswerCard', 'SourceList'],
        'tone': 'structured, step-by-step',
        'allowed_widgets': ['QueryTrail', 'AnswerCard', 'GuidedSteps', 'KeyFactsList',
                            'SourceList', 'ClarifierChips', 'FollowUpChips'],
        'proactive': {'clarifiers': True, 'followups': True, 'breathing_nudge': False},
        'tokens': {'targetScale': 1.1, 'typographyScale': 1.06, 'lineHeight': 1.66, 'accent': 'mild'},
    },
}


def get_policy(name):
    """Full policy dict for a state name (or 'neutral'); unknown names -> neutral."""
    name = name if name in _POLICIES else 'neutral'
    p = copy.deepcopy(_BASE)
    for k, v in _POLICIES[name].items():
        p[k] = copy.deepcopy(v)
    p['name'] = name
    return p


def policy_for(fused_state, condition):
    """Control (A) is prompt-only: always neutral, whatever the user's state."""
    if condition == 'control' or not fused_state:
        return get_policy('neutral')
    return get_policy(fused_state)


POLICY_NAMES = tuple(_POLICIES)
