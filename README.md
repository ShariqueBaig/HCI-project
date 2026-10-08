# Aura UI - Developer Guide

## Development Setup

1. Ensure you have Python installed.
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. To run the app during development, execute:
   ```bash
   python run.py
   ```
   *Any changes to the code can be tested instantly by closing the app and re-running this command.*

## Secrets & Spotify Integration
To enable the Spotify volume auto-lowering features, you need a `secrets.json` file in the root directory. This file is intentionally ignored by git to keep your API keys secure. 

Format for `secrets.json`:
```json
{
  "spotify_client_id": "YOUR_ID",
  "spotify_client_secret": "YOUR_SECRET",
  "spotify_redirect_uri": "http://localhost:8080"
}
```

## Exporting the `.exe` (Building)

When you are finished making code changes and want to generate a standalone executable for users, use PyInstaller. 

Run the following command in the terminal:
```bash
python -m PyInstaller --onefile --noconsole --name "AuraUI" run.py
```

Once the process finishes:
- The compiled standalone executable will be located in the `dist/` folder as `AuraUI.exe`.
- This is the **only** file you need to share with end users. They do not need Python or any other files installed. 

**Note on Git:** 
The `dist/` and `build/` directories, as well as `settings.json` and `.cache`, are automatically ignored by git so you don't accidentally push the compiled binaries or your personal application preferences to the repository.
