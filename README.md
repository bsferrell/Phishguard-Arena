# PhishGuard Arena

## Installation and local setup

### Prerequisites

- [Git](https://git-scm.com/downloads) and [Python 3.13](https://www.python.org/downloads/), with pip and SQLite FTS5 support.
- A web browser. The app runs locally using Streamlit.
- Optional: a [Gemini API key](https://aistudio.google.com/apikey) and internet access for AI-powered scenario selection and tutoring.

### 1. Clone the repository

Open Terminal on macOS or PowerShell on Windows:

```shell
git clone https://github.com/bsferrell/Phishguard-Arena.git
cd Phishguard-Arena
```

### Optional: use a setup script

Instead of the manual steps below, run the script for your platform from the project folder.

**macOS:**

```shell
sh setup.sh
```

**Windows (PowerShell):**

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

Once setup succeeds, optionally configure Gemini as described in step 4, then run the start command printed by the script. The Windows command bypasses the execution policy for that PowerShell process only.

The scripts create or reuse `.venv`, install dependencies, check SQLite FTS5, and seed the database only if `data/phishguard.db` does not already exist. The repository includes an existing database; the scripts leave it and any existing progress unchanged. To create a fresh database, first move the existing file somewhere safe, then rerun the script. Neither script creates an API key; see the optional Gemini configuration below. If installation fails, see the troubleshooting guidance in step 3.

### Manual setup

If you used a setup script, skip to step 4 to optionally configure Gemini, then start the game using the command above.

### 2. Create and activate a virtual environment

**macOS:**

```shell
python3.13 -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell):**

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, allow local scripts for the current user with `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then activate again. Alternatively, use Command Prompt and run `.venv\Scripts\activate.bat`.

### 3. Install dependencies

With the virtual environment active, run on either platform:

```shell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If `cryptography` fails to build because OpenSSL cannot be found, first try installing a compatible prebuilt wheel, then retry the requirements:

```shell
python -m pip install --only-binary=:all: "cryptography>=38.0.3"
python -m pip install -r requirements.txt
```

If no compatible wheel is available on macOS, install OpenSSL and pkg-config with [Homebrew](https://brew.sh/), then retry:

```shell
brew install openssl@3 pkg-config
OPENSSL_DIR="$(brew --prefix openssl@3)" python -m pip install -r requirements.txt
```

The OpenSSL libraries must match the Python interpreter's architecture (for example, x86_64 or arm64).

### 4. Configure Gemini (optional)

To enable AI-powered features, create a file named `.env` in the project root containing:

```text
GEMINI_API_KEY=your_api_key_here
```

Keep the key private; `.env` is ignored by Git. Without a key, or if the Gemini service is unavailable, the game uses its local scenario picker and template-based tutor instead.

### 5. Seed the database and start the game

Run these commands from the project root:

```shell
python check_fts5.py
python seed_db.py
python -m streamlit run app.py
```

The first command checks that Python's SQLite supports FTS5. If it fails, use a Python installation with FTS5 enabled. The seed command loads scenarios and policy passages into `data/phishguard.db`. On an existing database with attempts, reseeding may fail due to database references; move the database somewhere safe first if you want to start fresh.

Streamlit opens the game in your browser, usually at [http://localhost:8501](http://localhost:8501). If it does not open automatically, use the local URL printed in the terminal. Stop the server with `Ctrl+C`.

For later sessions, open a terminal in the project folder, activate the virtual environment as shown above, and run `python -m streamlit run app.py`.

## About the game

PhishGuard Arena is a phishing-awareness training game set at a fictional hospital. In each round, decide whether an email or text message is safe or phishing, select its warning signs, and rate your confidence. The game scores your answer, provides feedback and tutoring when needed, and tracks your points, difficulty level, and mastery of warning signs. Scenario selection adapts to your progress.

The game stores scenarios, attempts, and progress in a local SQLite database. You can enable **Show agent notes** in the sidebar to see whether the orchestrator or the local picker chose a scenario.

## Running tests

With the virtual environment active:

```shell
python -m pytest
```