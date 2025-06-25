Excellent. Delegating the initial development to an assistant while I supervise is a very efficient way to work.

Here is the prompt I have prepared for Claude. It contains all the necessary context, requirements, and instructions to ensure the `build_manifest.py` script is built correctly and according to the standards we've defined in the PRD.

***

Hello Claude,

We are beginning Phase 1 of the Scribe Viewer web application project. Your first task is to create the Python pre-processing script that will serve as the foundation for the entire application.

**Your assignment is to create the `build_manifest.py` script.**

This script's primary responsibility is to scan our existing `scribe` project data, process it, and generate a single, comprehensive `manifest.json` file. This manifest will be the sole data source for the Next.js front-end.

Please adhere to the following instructions precisely.

### **1. Core Requirements & Context**

*   **Primary Source of Truth:** The project's requirements, data structures, and goals are defined in the PRD. Please read it carefully before you begin: `docs/PRDs/scribe-viewer-webapp.md`.
*   **File Location:** Create the new script at `scribe-viewer/scripts/build_manifest.py`.
*   **Final Output:** The script must generate a single file named `manifest.json` and place it in `scribe-viewer/public/manifest.json`.

### **2. Detailed Implementation Steps**

**Step 1: Get the List of Files from the Database**
The canonical source for all interviews is the project's central database.
- Import the `Database` class from `scribe/database.py`.
- Use the `db.get_all_files()` method to retrieve a list of all file records. Each record contains the `file_id` and, most importantly, the `original_path` of the media file.

**Step 2: Intelligently Parse Metadata from Filenames**
For each file record from the database, you must attempt to parse metadata from the `original_path`.
- Use regular expressions to extract information like `date` and `interviewee`.
- **Example:** For a filename like `.../Rigg-interviews/2024-01-15_Max_Mustermann_Interview_123.mp4`, you should be able to extract:
    - `date`: "2024-01-15"
    - `interviewee`: "Max Mustermann"
- Please create a flexible function to handle different filename patterns. If no metadata can be parsed, use placeholder values (e.g., "Unknown Interviewee").

**Step 3: Convert SRT Files to VTT**
The web requires the `.vtt` format for subtitles. Your script must handle this conversion.
- For each language (`en`, `de`, `he`), find the corresponding `.srt` file in the `output/<file_id>/` directory.
- Create a helper function that reads an `.srt` file and saves a new `.vtt` file in the same directory.
- You may use the `webvtt-py` library for this. Please add it to a new `scribe-viewer/scripts/requirements.txt` file.

**Step 4: Generate Transcript Cues**
For the synchronized highlighting feature, the manifest needs a `cues` array for each transcript.
- After converting to VTT, parse the `.vtt` file for each language.
- For each caption in the VTT file, extract its start time and its text content.
- Create a list of cue objects in the format `{ "time": <start_time_in_seconds>, "text": "..." }`.

**Step 5: Assemble the `manifest.json`**
Iterate through every file from the database and assemble a JSON object for each one that precisely matches the structure specified in the PRD under "Section 7. Data Structure". This includes:
- The `id` (file_id).
- The parsed `metadata`.
- The `assets` object, with a relative path to the video file and the newly created `.vtt` subtitle files.
- The `transcripts` array, containing the full transcript text and the `cues` array for each language.

### **3. Final Output & Deliverables**

1.  **The Script:** A clean, well-commented Python script at `scribe-viewer/scripts/build_manifest.py`. It should have a `main` function and be executable from the command line.
2.  **Requirements File:** A `scribe-viewer/scripts/requirements.txt` file containing any necessary libraries (e.g., `webvtt-py`).
3.  **Your Summary:** Upon completion, please provide me with a summary of your work. The summary should include:
    *   A brief overview of how the script functions.
    *   The libraries you chose to use.
    *   Clear instructions on how to run the script from the command line.

I will review your summary first, and then I will review the code you have produced.

Proceed with the assignment.

***

This prompt is now ready. I will monitor the ongoing English evaluations and will proceed with the Hebrew evaluations as soon as the English process is complete. In the meantime, I am ready for any other instructions you may have.