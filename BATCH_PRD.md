Product Requirements Document: Multi‑Language Batch Transcription Tool

Introduction & Purpose

This PRD outlines the enhancements to the existing Video to Text Transcription Tool to support bulk transcription of audio/video files with multi-language outputs. The current script processes a single file or a flat directory and transcribes it in one language via ElevenLabs Scribe v1. The enhanced tool will accept whole folders (including subfolders), handle files with complex names safely, and produce transcripts in multiple languages for each file. These improvements aim to streamline batch processing and broaden the tool’s usability for multilingual transcription needs.

Objectives and Goals
	•	Recursive Folder Input: Allow users to specify a directory (with nested subdirectories) containing audio/video files, instead of single files only.
	•	Filename Sanitization: Ensure files with special characters in names are handled safely by sanitizing names for processing, while preserving original names in reports.
	•	Pre-Processing Summary: Before transcription begins, display a summary of how many files were found, total duration of media, and an estimated transcription time for transparency.
	•	Multi-Language Transcription: For each media file, generate transcripts using ElevenLabs Scribe v1 in the audio’s native language (auto-detected) as well as German, English, and Hebrew.
	•	Transcript & Subtitle Outputs: For each file and each target language, output a plain text transcript and an .srt subtitle file.
	•	Organized Output Structure: Save results using sanitized filenames and directory structure to avoid issues with file systems, grouping outputs logically per file or language.
	•	Final Summary Report: After processing, produce a comprehensive report (in both Markdown and CSV format) listing each file’s original name, sanitized name, detected language, duration, success/failure status, and which languages were transcribed successfully.
	•	Performance & Reliability: Implement best practices for scanning directories efficiently, estimating transcription time based on audio length, sanitizing file paths safely across operating systems, structuring outputs clearly, and using the ElevenLabs API effectively at scale.

Feature Requirements and Specifications

1. Recursive Directory Scanning for Media Files

Requirement: The tool must accept a directory path as input and recursively find all audio and video files within that directory and its subfolders. It should support common video formats (e.g. .mp4, .mov, .avi, .mkv, .webm) and audio formats (e.g. .mp3, .wav, .m4a, .flac, .ogg).

Details:
	•	Use an efficient method (such as Python’s os.walk or pathlib.Path.rglob) to traverse subdirectories and gather files ￼ ￼. This ensures all nested files are discovered without needing manual user input for each subfolder.
	•	Filter the discovered files by extension to include only supported audio/video types. Maintain two categories internally (audio vs video) to handle them appropriately during processing (video files will need audio extraction, audio files can be transcribed directly).
	•	Counting: Count the total number of files found. Also count how many are video vs audio for the summary report (e.g., “Found 10 files: 6 videos and 4 audio files”).

Best Practice: Using Path().rglob("*.ext") for each extension or a unified pattern is a simple approach to recursive search ￼. This avoids writing custom recursion and is cross-platform. Ensure hidden files or system files are ignored unless needed.

Alternate Consideration: The current script’s process_directory function only looks for videos in a non-recursive manner ￼. The new implementation will improve this by true recursion. If performance becomes an issue with extremely large directory trees, consider allowing a file extension filter or a maximum depth setting, though typically recursion with a generator is efficient and can handle large numbers of files in a memory-efficient way.

2. Filename Sanitization for Safe Processing

Requirement: Many file systems have restrictions on filenames (for example, Windows disallows characters like \ / : * ? " < > |). The tool should sanitize filenames for any files it processes or creates, removing or replacing problematic characters so that file operations and output creation do not fail. Crucially, the original filename should be preserved in logs and reports for user reference.

Details:
	•	Define a sanitization function that takes a filename (or path) and returns a “safe” version. This typically involves removing or substituting characters such as spaces, commas, semicolons, parentheses, brackets, and other symbols that might cause issues in shell commands or as part of file paths ￼. For example, "Project Plan (Draft).mp4" might be sanitized to "Project_Plan_Draft.mp4".
	•	Also handle non-printable or Unicode characters. Either remove them or replace with a safe placeholder. The goal is a sanitized name consisting of alphanumeric characters, underscores or hyphens, and dot for the extension ￼. It’s also wise to trim leading/trailing whitespace or dots from names, as those can cause issues on Windows ￼.
	•	Ensure the sanitized names are unique within the output context to avoid collisions. If two different original files sanitize to the same name (e.g., “data?.mp4” and “data*.mp4” could both become “data.mp4” after removing ? and *), the tool should detect this and differentiate them (for instance, by appending an index or a hash).
	•	Preserving Original Names: Maintain a mapping of original filename to sanitized filename. Use this in the final summary so the user can see the original names. Do not lose the original reference; the sanitized version is only for safe processing and output file naming.

Implementation Suggestions:
	•	Consider using a well-tested library for filename sanitization if available. For example, the pathvalidate library can sanitize filenames to be safe on all platforms, removing invalid characters and reserved names ￼ ￼. This can simplify implementation and ensure edge cases (like device names CON, NUL on Windows) are handled ￼.
	•	If not using a library, implement a whitelist approach: allow letters, numbers, and a short list of symbols (e.g. _ and -), and replace anything else with an underscore or similar. For instance: re.sub(r'[^A-Za-z0-9._-]', '_', filename) will replace any unsafe character with _ ￼. Additionally, you might replace spaces with _ for consistency.
	•	Log or print a warning when a filename gets sanitized, so the user knows (optional but useful for transparency). For example: “Sanitizing filename: Project Plan (Draft).mp4 → Project_Plan_Draft.mp4”.

Cross-Platform Consideration: The sanitization should target a universal safe set of characters. Using the universal mode of sanitization (as in pathvalidate) ensures the name is valid on Windows, Linux, and macOS ￼. This avoids subtle issues like : which is allowed in Linux but not Windows, etc. Ensuring the output directory and filenames adhere to these rules prevents errors when the user tries to open results on a different OS.

3. Pre-Processing Summary Report (Terminal)

Requirement: Before starting the transcription of files, the tool should display a summary in the terminal. This summary includes:
	•	File counts: The number of video files and audio files found (and perhaps total count).
	•	Total duration: The combined length of all audio tracks (sum of durations of each file).
	•	Estimated transcription time: A rough prediction of how long the transcriptions might take to complete, given the total duration and the expected performance of the transcription API.

Displaying this upfront informs the user about the scope of the task (for example, “20 files (~3.5 hours of audio) found. Estimated transcription time: ~15 minutes.”). It allows them to confirm the input is as expected and decide if they have time to proceed.

Details:
	•	Duration Calculation: For each media file found, determine its duration in seconds. Sum these values for a total duration. Duration can be obtained without fully processing the file by reading metadata. For example, using ffmpeg.probe (via ffmpeg-python or direct ffprobe command) can fetch the duration of audio/video streams very quickly ￼. This avoids needing to load the entire file into memory just to get length. If using moviepy for video processing, one can use VideoFileClip.duration for videos and a similar approach for audio files, but doing so for many files might be slower than a metadata probe.
	•	Duration Formatting: Convert the total seconds into a human-readable format (e.g., hours, minutes). For instance, 3665 seconds would be shown as “1h 1m 5s” or “~61 minutes”. This gives the user an intuitive sense of scale.
	•	Transcription Time Estimation: Estimating how long the API will take can be tricky, but a simple heuristic can be used. For example, ElevenLabs Scribe v1 is high-accuracy but not real-time streaming ￼, so processing might be roughly on the order of the audio length or slightly faster. A conservative estimate could assume 1× to 1.5× real-time for transcription. If total audio is 60 minutes, estimate ~60–90 minutes of processing by the API. In practice, Scribe may outperform real-time – reports suggest it’s optimized for batch accuracy rather than speed, yet it’s still quite fast. For instance, if Scribe processes an hour of audio for $0.40, it’s likely leveraging powerful servers and could transcribe significantly faster than an hour, perhaps in just minutes. Without exact figures, the tool might estimate using a factor (e.g., assume ~0.5× real-time, meaning 60 minutes audio ~30 minutes processing). This estimate should be clearly labeled as an approximation.
	•	Display: Print lines such as:
	•	“Audio files found: X, Video files found: Y (Total: Z files)”
	•	“Total audio duration: HH:MM:SS (e.g., 02:45:30)”
	•	“Estimated transcription time: ~N minutes” (or hours, as needed).
	•	Also include a note that actual transcription time may vary based on network and API processing speed.

Best Practices & References:
	•	Using media metadata for duration is efficient. For example, ffmpeg.probe yields a JSON with stream info including duration ￼. Filtering for the audio stream duration is shown in the example where they extract stream['duration'] for the audio track ￼. This method is much faster than decoding the entire file and is accurate.
	•	If ffmpeg is not available, alternatives include pydub or mutagen for audio, or using OpenCV/MoviePy for video. pydub.AudioSegment can load just the header of an audio file to get duration_seconds ￼, but be cautious with very large files as it may attempt to read more data.
	•	The estimated time calculation can be refined if empirical data is available. For example, if in testing we observe that Scribe transcribes 1 minute of audio in ~5 seconds on average, we could use that ratio (5 sec per minute -> 12× speed-up, so 60-minute audio ~5 minutes). In absence of such data, err on the safe side to not underestimate. Additionally, note that performing four transcriptions per file (for four languages, see next sections) means the total processing time is roughly four times the single-language estimate. The summary can either present the time per language or the total including all languages. It might be clearer to estimate the total time for all outputs. For example: “Estimated transcription time (all languages): ~20 minutes” if one language would be ~5 minutes for all files.

User Confirmation (Optional): Optionally, after printing the summary, the script could prompt the user to continue or abort (especially if the estimated time or file count is very high). This is a user-experience consideration to avoid unexpected long runs.

4. Multi-Language Transcription per File

Requirement: Each audio/video file should be transcribed in multiple languages:
	•	The file’s original language (automatically detected by Scribe), and
	•	German (deu), English (eng), and Hebrew (heb) transcripts regardless of the original language.

This means for every input file, the output will include four different transcripts (one in the source language and three in the specified target languages).

Details & Workflow:
	•	Language Detection: Leverage ElevenLabs Scribe’s automatic language detection for the first transcript. This is achieved by calling the API with language_code=None (or passing no language, which triggers auto-detection). According to ElevenLabs documentation, if language_code is not provided, Scribe will detect the spoken language automatically ￼. The returned transcription object typically includes a detected language code or can be inferred. For example, the API may return a field like "language_code": "en", "language_probability": 1.0 indicating it detected English ￼. We will capture this detected language and include it in the reports.
	•	Transcription Calls: After getting the original-language transcript, perform additional transcription/translation tasks for German, English, and Hebrew outputs. Important: ElevenLabs Scribe v1 is fundamentally a speech-to-text model, not a general translator. It expects the language_code parameter to match the language spoken in the audio ￼. Therefore, producing a transcript in a language different from the spoken audio requires a different approach:
	•	If the original audio is already in one of the target languages (e.g., audio in English, and we also need English transcript), then the auto-detected transcript covers it. We would skip re-transcribing English since it’s duplicate of the original in that case. Similarly, if the audio was in German or Hebrew originally, the auto transcript handles that language.
	•	If the target language is different from the spoken language (e.g., audio in Spanish, but we need an English transcript), Scribe alone cannot directly produce an English translation because it’s designed to transcribe what is heard, not translate content ￼. Attempting to call convert with language_code="eng" on Spanish audio would likely yield incorrect results (it would try to interpret Spanish speech as if it were English speech, resulting in gibberish). Thus, we need a translation step.
	•	Translation Mechanism: For each target language that is not the original language:
	•	First, get the original transcript text via Scribe (auto mode).
	•	Then use a reliable translation method to convert that text to the target language. This could be an external API or library (e.g., Google Translate API, DeepL API, or open-source models). This translation should be done on the text, not via Scribe. By doing this, we ensure accuracy of the initial transcript and then leverage specialized translation tools for language conversion, since ElevenLabs does not provide text translation in the transcription API ￼.
	•	Another approach could be to use OpenAI’s Whisper model in “translate” mode for those languages, but that would complicate the pipeline by introducing another ASR system. It’s cleaner to use text translation on the Scribe output.
	•	Note: ElevenLabs has an AI Dubbing feature (voice translation) that can dub content into other languages while preserving voice ￼ ￼. However, that is a separate product (focused on generating audio in another language) and not directly accessible via the Scribe API for text transcripts. It’s not intended for extracting a written translation. Therefore, we will not rely on that for this tool (though it’s worth noting for context).
	•	API Calls per File: The process for each file will be:
	1.	Extract audio (if input is video – see next section for details on extraction).
	2.	Transcribe original (auto-detected language) – one API call with language_code=None ￼.
	3.	For each target language (deu, eng, heb):
	•	If the target equals the detected language, skip (already obtained).
	•	Else, either use Scribe in forced mode or use translation:
	•	Preferred: Use text translation on the original transcript to the target language.
	•	Alternative: (Not recommended) Use Scribe with language_code=<target> on the same audio. This likely yields poor results unless the audio actually contains that language. We note this as a potential misunderstanding in the original requirements. The proper way is translation after transcription in the source language.
	4.	Collect all transcripts (original + translations).
	5.	Generate subtitles for each transcript.
	•	Parallelization: These multiple transcription tasks per file could be done sequentially or in parallel. To keep implementation simple and avoid complicating API usage, the initial approach can be sequential (one language after another). The performance impact is that processing four transcripts per file quadruples the time per file. If this becomes a bottleneck for many files, we can consider parallelizing the API calls for different languages using threads or async calls, since they are independent. However, we must be mindful of API rate limits and the system’s ability to handle multiple large uploads at once. For now, sequential calls per file is safer and ensures we don’t overload the API (ElevenLabs hasn’t documented strict rate limits, but caution is advised).

Best Practices & Considerations:
	•	Reusing Audio Data: Uploading the audio to the API is a significant part of each call’s overhead. The current script reads the entire audio file into a BytesIO object to send it ￼. To avoid reading the same file from disk multiple times for each language, we can read it once and reuse the in-memory bytes. For example, load the audio file into memory (or keep the extracted audio file path) and for each subsequent convert call, reset the BytesIO stream to the beginning (audio_data.seek(0)) and re-send it. This way, the file is only read from disk one time per file. This improves efficiency when doing back-to-back calls on the same file.
	•	Diarization and Timestamps: Continue to use diarization for speaker labels and word-level timestamps in Scribe calls (the current script sets diarize=True and timestamps_granularity="word" ￼). This is useful for creating accurate subtitles. We should confirm that the diarization and timestamps work for all languages similarly. Scribe supports diarization up to 32 speakers ￼, which should suffice for most use cases like meetings or interviews.
	•	API Model and Parameters: Always specify the model_id="scribe_v1" (currently the only model) and tag_audio_events=True to label non-speech sounds (e.g., “[laughter]”) ￼. These tags should appear in the transcript text. If needed, they can be translated or left as is in translations (e.g., “[laughter]” might remain the same token).
	•	Error Handling: If a transcription API call fails (network error, API error, etc.), catch the exception and record the failure. The tool should not abort the entire batch if one file or one language fails; instead, mark that file’s particular output as failed and continue with others. For example, if English translation fails but others succeeded, the final summary for that file might indicate “Partial success: failed for English”. This way one problematic file or service interruption doesn’t halt the whole batch.
	•	ElevenLabs Cost Consideration: Each transcription call costs money (as of TechCrunch, $0.40 per hour of audio ￼). Doing four per file quadruples cost. This should be documented (perhaps not in the PRD, but for user awareness) to avoid surprise. The benefit is the multi-language result, but the user might want an option to choose which languages to generate to control cost. Future enhancement: Make the languages configurable (via command-line arguments or config), so the user can specify a subset or additional languages as needed. For now, German, English, Hebrew are fixed per requirements, but the design can keep this extensible.

Alternative Approaches:
	•	We considered using the ElevenLabs Scribe API in a perhaps unintended way to get other languages, but as noted, it’s not a translation API. The chosen approach (transcribe once, then translate text) ensures accuracy and uses the best tool for each job (ASR for transcription, MT for translation). This is a better practice than trying to re-transcribe audio with a false language code, which would produce incorrect output given Scribe’s design ￼.
	•	Another alternative is using a different multilingual ASR that directly provides translation (e.g., OpenAI Whisper has a mode to output English for any input language). However, Whisper is less accurate than Scribe in many cases ￼ and would complicate the pipeline (introducing two different AI services). Since the requirement is specifically to use ElevenLabs Scribe, sticking with Scribe + separate translation meets the goal.

5. Audio Extraction for Video Files

(This feature is inherited from the current script but worth specifying for completeness and potential improvements.)

Requirement: When an input file is a video, its audio track must be extracted before transcription, as the ElevenLabs API needs audio input. The tool will extract audio to a temporary file (or memory) and then send that audio for transcription. If the input file is already an audio format, this step is skipped (we use it as-is).

Details:
	•	The current implementation uses MoviePy (VideoFileClip) to read the video and write out an audio file (MP3) ￼. This approach works, but there are considerations:
	•	MoviePy uses FFMPEG under the hood and can handle most formats. It writes out an audio file using video.audio.write_audiofile(...) ￼. By default, the script chooses MP3 with a given path or a temporary file.
	•	We should ensure that problematic filenames are sanitized before calling MoviePy, to avoid issues with ffmpeg handling those names. (Alternatively, pass the file path with proper quoting if possible.) Using a sanitized temporary path (maybe in the system temp dir) is safest.
	•	For large video files, extraction can take time. A progress indicator is already printed (“Extracting audio… Done”) in the current script ￼. We can retain or enhance such feedback (for example, showing a tqdm progress if extraction can report progress). However, ffmpeg via MoviePy doesn’t easily give progress callbacks, so a simple print is fine.
	•	Audio Format: The script currently extracts to MP3 by default ￼. MP3 is a lossy format; using it means the audio is re-encoded before transcription, potentially losing some quality. Best practice for speech-to-text is to use a lossless format like WAV if possible, to maximize transcription accuracy. We could consider extracting audio as WAV (PCM) to avoid any quality loss. The trade-off is file size (WAVs are larger). Given Scribe’s high accuracy, the difference might be minimal unless the audio is on the edge of intelligibility. If using MP3 (which compresses to smaller size), it might actually speed up upload and reduce cost (since less data to send). Decision: We can stick to MP3 for now (as per current script), since it hasn’t been flagged as an issue, but note that WAV is an option if accuracy issues arise.
	•	Keeping or Deleting Audio Files: Provide an option (as the current script does with --keep_audio) to retain the extracted audio file in the output directory. By default, after transcription, the temporary audio file should be deleted to save space ￼. However, if the user wants to inspect or reuse the audio, they can choose to keep it. The PRD focuses on transcripts, but we will maintain this feature from the original tool for completeness.

Performance Consideration: If processing many video files, extraction can be parallelized or optimized:
	•	Using ffmpeg directly via subprocess might be faster than MoviePy for batch operations, because we could use the -vn (no video) flag to copy or encode audio in one step. For example: ffmpeg -i input.mp4 -vn -acodec mp3 output.mp3. This avoids loading the video into Python memory. If performance becomes a bottleneck, switching to direct ffmpeg calls could be an improvement.
	•	Alternatively, one could extract audio and transcribe in one streaming step (not with Scribe alone, but conceptually using ffmpeg to stream audio frames to the API). However, the ElevenLabs API expects a complete file upload, not a streaming socket, so this is not applicable.
	•	Ensure the extraction uses the sanitized name for the output audio to avoid filesystem issues. For example, if original video is My:Video?.mp4 (unsanitized), and sanitized is My_Video_.mp4, then audio could be extracted as My_Video_.mp3 in a temp or output folder.

6. Transcript and Subtitle Generation

Requirement: For each file and each target language, generate:
	•	A plain text file containing the full transcript text.
	•	An SRT subtitle file with timestamps and (if available) speaker labels.

The outputs make the transcriptions usable for reading and for subtitle overlay on videos.

Details:
	•	Transcript Text File (.txt): This is a straightforward dump of the transcription text. For consistency, include any non-speech tags (e.g., “[laughter]”) and diarization labels if they are integrated in the text. (The ElevenLabs transcription.text property likely returns a single coherent transcript string with punctuation and possibly line breaks. We can use it directly ￼.) Each transcript file should be saved with a name that indicates the language. For example:
	•	If the sanitized base name of the file is example_video, we could save:
	•	example_video.eng.txt for English transcript,
	•	example_video.deu.txt for German,
	•	example_video.heb.txt for Hebrew,
	•	example_video.spa.txt (if original was Spanish, using ISO language code for original), or example_video.orig.txt as a generic label for the original language.
We need a convention: using ISO 3-letter codes (eng, deu, heb, etc.) is clear and avoids ambiguity, especially since “heb” (Hebrew) might use a non-Latin script in the text but we keep filename in Latin characters. Using .orig.txt could be ambiguous if we always produce it (better to use the actual detected code if known, e.g., fra.txt for French). Since Scribe can detect language, we have that code. We will use the detected language’s ISO 3-letter code for the original transcript file name. In reports, we’ll list the full language name or code.
	•	Subtitle File (.srt): We will use the word-level timestamps from Scribe to build subtitles. The current script already has a function create_srt_subtitles(transcription) that iterates over transcription.words (each word has start/end) and groups them into subtitle captions respecting a max characters per line and speaker changes ￼ ￼. We will reuse and refine this:
	•	The function should produce a valid SRT content as a string, which is then written to a .srt file. It numbers the captions sequentially and gives start –> end times in HH:MM:SS,ms format ￼.
	•	It also prefixes subtitle text with speaker identification if diarization is on (e.g., “Speaker 0: Hello world”). This is useful for multi-speaker audio. We should ensure that if speaker IDs are numeric or generic, the format remains consistent. (We might consider mapping speaker_0, speaker_1 to A, B or some nicer labels, but that’s a nice-to-have; using the IDs is fine).
	•	The max characters per line (40 in the script) is a reasonable default. We could keep it configurable, but it’s fine as is. The logic breaks lines either when too long or on speaker change ￼, which is a reasonable heuristic.
	•	We should verify that the logic handles different languages scripts (e.g., right-to-left text for Hebrew). SRT is plain text, so Hebrew characters should be fine, but ordering and line splitting should consider that it’s RTL. We might not delve into reversing the text; it should appear correctly as long as the text is written to the file in UTF-8 (which we will ensure by using encoding='utf-8' when writing ￼). Most subtitle players handle RTL text display appropriately.
	•	If, for some reason, word-level timestamps are not available (Scribe’s API might omit word breakdown for some languages or if diarize is off), the function should handle it gracefully. The current script checks if not hasattr(transcription, 'words') or not transcription.words: and warns if so ￼. In such cases, an SRT cannot be created, and we’d log that. However, since we are enabling timestamps_granularity="word" and Scribe supports word timestamps in all 99 languages ￼, we expect this to be available.
	•	File Organization: There are two main ways to organize output files:
	1.	Single Output Directory: Put all transcript and subtitle files for all inputs into one output folder. This was the approach in the original script (all outputs go into the specified --output directory, each named by the input’s base name). In a batch scenario with multiple languages, this could lead to dozens of files, but as long as they’re named clearly, it’s manageable.
	2.	Subdirectory per Input File: Create a subfolder (perhaps named after the sanitized file base) under the output directory, and put that file’s various outputs inside. For example, output/example_video/ example_video.eng.txt, example_video.eng.srt, example_video.deu.txt, .... This groups related files together. This approach scales better if there are many files, preventing a flat flood of files. It also avoids naming collisions if two input files share the same name. For instance, lecture.mp4 and lecture.mp3 in different subfolders would both sanitize to lecture – in a flat output, you might get collisions like lecture.txt from each. If each input gets its own folder, we avoid that.
We propose using Option 2: subdirectory per input file in the output folder. The subdirectory can be named as the sanitized base name (or even include an index if needed to ensure uniqueness). Within it, files can be named with just the language suffixes, e.g., eng.txt, eng.srt, deu.txt, deu.srt, orig.txt, orig.srt. Alternatively, keep the full name in each. To keep things simple, we might still include the base name in the file name (so example_video.eng.txt rather than just eng.txt), in case someone moves files around outside the folder, they carry context.

Writing Files:
	•	Ensure all text is written in UTF-8 encoding to support non-English characters (the current code does this when writing transcripts ￼).
	•	Double-check that newline handling is correct for subtitles (SRT requires CRLF or LF consistently; LF is fine). Each caption block in SRT ends with a blank line ￼, which the code already handles.
	•	After writing, print a log line indicating success (e.g., “Transcription saved to: …”, “Subtitles saved to: …” as in current script ￼). This real-time feedback per file is useful for the user to track progress in the console as files complete.

Verification:
	•	Test with a small video to ensure the transcripts and subtitles align (perhaps manually spot-check a segment).
	•	Test with a file with a tricky name to ensure sanitization and file writing works (e.g., “test,video?.mp4” results in a folder test_video_ and files inside it).

7. Output Filenames and Directory Structure

Requirement: The output filenames and folders should be systematically generated, using sanitized names to avoid errors, and structured for clarity. The original names should be traceable via the final report, but the actual file system entries (directories/files) should use the sanitized versions.

Details:
	•	Main Output Directory: If the user specifies an output directory (via an argument, e.g., --output), use that as the root for all outputs. If not specified, default to something like ./transcripts or simply the current directory. Always ensure the directory exists (create with os.makedirs(..., exist_ok=True) before writing files ￼).
	•	Subdirectory per File: As discussed, create a folder for each input file’s outputs. The folder name can be the sanitized base filename (without extension). For example, My_Video_2021 for input My Video (2021).mp4. If there are multiple files with the same base name, append a suffix to differentiate (e.g., My_Video_2021_1, My_Video_2021_2). However, if the input files are in different subdirectories originally, we might mirror that structure to avoid collisions:
	•	We could reconstruct the relative path inside the output. For example, if the input folder is Conference/ and it has Day1/intro.mp4 and Day2/intro.mp4, output could be Output/Day1/intro/intro.eng.txt... and Output/Day2/intro/intro.eng.txt.... This mirrors the input structure and ensures uniqueness. This approach increases complexity but is user-friendly for matching outputs to inputs. Another simpler way is to include part of the path in the name (like Day1_intro.txt vs Day2_intro.txt if we flatten). Mirroring directories is cleaner.
	•	For this PRD, we’ll favor mirroring the input directory structure under the output directory, using sanitized folder names as needed. This means using os.walk or pathlib to get relative paths. Each subdirectory in input would be created in output (sanitized). This way, the context of files is preserved.
	•	Filename Scheme for Transcripts/Subtitles: Within each file’s folder:
	•	Base name (sanitized, no extension) + . + language code + . + extension.
	•	Use consistent language codes: we’ll use ISO 639-3 codes as given by ElevenLabs (e.g., "deu" for German ￼, "eng" for English, "heb" for Hebrew, and whatever code Scribe detects for the original if not one of those).
	•	Example: for Project_Plan_Draft.mp4 (sanitized from “Project Plan (Draft).mp4”), suppose the audio is in English. We create:
	•	Project_Plan_Draft/orig.eng.txt (or we could call it just Project_Plan_Draft.eng.txt – since orig is also eng, this is redundant. Possibly we label it orig only when original language is not one of the others? This might complicate naming. Simpler: do not use “orig” in the filename, just use the actual language code for everything. In this example, original language code is eng, and we also have an English target. We might skip separate call, but file-wise, we have one English transcript. We won’t duplicate it. So it’s just Project_Plan_Draft.eng.txt and .eng.srt which serve both as original and English output.)
	•	Project_Plan_Draft.deu.txt & .deu.srt
	•	Project_Plan_Draft.heb.txt & .heb.srt
If original language was Spanish (code “spa”), then outputs:
	•	Project_Plan_Draft.spa.txt & .spa.srt (original)
	•	Project_Plan_Draft.eng.txt & .eng.srt (English translation)
	•	Project_Plan_Draft.deu.txt & .deu.srt (German translation)
	•	Project_Plan_Draft.heb.txt & .heb.srt (Hebrew translation)
This consistent naming allows programmatic identification of files by language code.
	•	Sanitization in Paths: Use sanitized names for both folder and file names. E.g., if an input subfolder is named Conferences/Day 1/ (with space), output can sanitize Day_1. If a file name has characters, we sanitize as earlier. This ensures no illegal paths are created on the filesystem.
	•	Avoiding Overwrite: If the output path already contains files from a previous run (maybe the user re-runs on the same directory), consider how to handle it:
	•	We could overwrite existing files (assuming the user wants an update).
	•	Or we could version them (not requested, probably unnecessary).
	•	At least, ensure that partial files from a previous run don’t confuse this run’s summary. It might be simplest to require a clean output directory or warn the user if it’s not empty. This is an edge consideration; likely overwriting is fine.

8. Final Summary Report (Markdown and CSV)

Requirement: After processing all files, generate a summary report in two formats: Markdown (for easy reading) and CSV (for spreadsheet or programmatic use). These reports will tabulate key information for each input file and the transcription outcomes.

Columns to include:
	•	Original Filename: The name of the file as it was in the input (including extension). If we processed files in subdirectories, include the relative path or at least the filename – perhaps the full relative path to distinguish same names. e.g., Day1/Intro.mp4. This helps identify files especially if there were duplicates.
	•	Sanitized Filename: The name/path used in processing/output. For clarity, this could be the path of the output folder or base name. If we mirrored structure, sanitized filename might be similar to original but with characters changed. Listing it shows exactly how to find the output on disk.
	•	Detected Language: The language detected by Scribe for the original audio. Use a human-readable name (and possibly code in parentheses). For example, “Spanish (spa)” or “English (eng)”. This confirms to the user what the audio was identified as. If the detection was wrong, the user might spot it here. (ElevenLabs is very accurate in detection ￼, so this is mainly informational.)
	•	Duration: The length of the audio in that file. Format this consistently, e.g., in seconds or HH:MM:SS. Since this was computed earlier, we can reuse that value. It’s useful to see durations per file in the final report to maybe correlate with any issues or just to know.
	•	Transcription Status: Indicate whether the transcription was successful. This could be a simple “Success” or “Failed”. If any of the requested outputs for that file failed, mark it as “Partial” or “Failed” with notes. For example, if the original and two translations succeeded but one language failed, mark “Partial” and perhaps detail which failed in the next column. If everything went fine, “Success”. If the file couldn’t be processed at all (e.g., audio extraction failed or API gave an error for even original), mark “Failed”.
	•	Languages Transcribed: List the languages that have been output for this file. Ideally, this should be all four (Original, DE, EN, HE) – but using names or codes. For instance: “Spanish, English, German, Hebrew”. If some failed, omit those or mark them specially (like adding “(failed)” after a language). The user can see exactly which transcripts are available. This column essentially reflects the files that were generated. It might also be useful to indicate the file count of outputs here, but listing languages is more direct.

Format specifics:
	•	Markdown Report: Use a Markdown table for clarity. For example:

Original File	Sanitized Name	Detected Language	Duration	Status	Outputs Generated
Day1/Intro.mp4	Day1/Intro.mp4	English (eng)	00:05:23	Success	English, German, Hebrew
Day2/Интервью.mkv	Day2/Intervju.mkv	Russian (rus)	00:45:10	Partial	Russian, English, German
song.mp3	song.mp3	Spanish (spa)	00:03:10	Success	Spanish, English, German, Hebrew

(The above is illustrative; note the second entry shows a case where maybe Hebrew failed, so it’s not listed, and status is Partial.)
Each row is a file. We align Duration to the right for numeric consistency, though Markdown will just render it as text (we can add the alignment colons in the table format as shown to indicate right alignment for duration).

	•	CSV Report: Use commas to separate the same fields. Ensure to quote fields that may contain commas (original filenames might contain commas or spaces, so proper CSV quoting is needed). The CSV can be easily opened in Excel or processed by scripts. The header row should be included. For example:

Original File,Sanitized Name,Detected Language,Duration,Status,Outputs Generated
"Day1/Intro.mp4","Day1/Intro.mp4","English (eng)","00:05:23","Success","English|German|Hebrew"
"Day2/Интервью.mkv","Day2/Intervju.mkv","Russian (rus)","00:45:10","Partial","Russian|English|German"
"song.mp3","song.mp3","Spanish (spa)","00:03:10","Success","Spanish|English|German|Hebrew"

Here I used | between languages in the last column to avoid confusion with the comma delimiter. Or we could just quote the whole list. Either way, ensure the CSV is valid.

	•	Saving Reports: Save summary.md and summary.csv in the main output directory (or perhaps offer the user to specify a path). If the output directory is per input file, we can place the summary at the root of that structure so it’s easily found. Print a message at end like “Summary report saved as summary.md and summary.csv”.
	•	Include Totals: Optionally, at the bottom of the Markdown report, we can add a line like: Total files processed: N (M successes, K partial, L failed). This gives a quick overall status. The CSV might not need this extra line as it’s more for data. But in Markdown it’s a nice human-readable closure.

Best Practices:
	•	Use the data collected during processing to fill this table. For each file processed, we will have stored: original name, sanitized name, detected language, duration, and a list of outputs or a dict of language->success. It’s wise to collect these in a structured object (like a list of dicts or a dataclass) as we go, then output at the end. This avoids recomputing anything.
	•	Ensure to handle characters properly in Markdown: e.g., if an original filename contains | or other Markdown syntax, escape it or put it in a code span. But filenames rarely contain the pipe character. Still, if a name contains backticks or pipes, escaping might be needed to not break the table. Probably a minor edge case.
	•	Citing in Document: If this PRD is delivered to stakeholders, the Markdown format in the report is meant for the output of the tool, not for the PRD itself. So don’t confuse the two; the PRD is a design doc and can itself use Markdown (as we are doing here) but the described output is separate.

Verification: After implementation, run the tool on a small set and open the summary.md to ensure the table is well-formed and all data appears correct. For CSV, open in a spreadsheet or use a CSV validator to ensure proper formatting.

Performance & Scalability Considerations

Efficient Directory Traversal

The approach using pathlib.Path.rglob or os.walk is efficient enough for most scenarios. It yields file paths one by one, which we then process. Memory usage is minimal (not storing the entire list at once unless we explicitly cast the generator to a list). If an input directory has tens of thousands of files, we should be mindful of memory and maybe process in streaming fashion. The design already leans toward processing each file in a loop as they are found, not holding everything in memory. This is good.

One consideration: if we want to sort the files (e.g., alphabetically) for deterministic output order, we might collect them in a list and sort. That’s fine for moderate numbers but could be memory heavy for huge counts. Alternatively, it’s not necessary to sort – processing order can just follow whatever os.walk yields (which is typically directory order). For user-friendliness, alphabetical might be nicer though.

Transcription Throughput and Parallelism

As mentioned, doing four API calls per file will be time-consuming for large batches. If we assume Scribe can handle perhaps one hour of audio in a few minutes, a batch of e.g. 10 hours total audio (600 minutes) with 4 languages might take roughly 4 * 600 = 2400 minutes of audio worth to process. If Scribe is, say, 5x faster than real-time, that’s 480 minutes (~8 hours) of actual processing. This is quite a lot for one thread. We might consider concurrent processing:
	•	Parallelize at the file level: e.g., process 2–3 files simultaneously in separate threads or processes. This can reduce wall-clock time but will increase CPU and network usage. The ElevenLabs API likely can handle multiple parallel requests (especially if they are on different connections). But we should confirm any rate limiting – since they charge per usage, they likely allow some concurrency, though heavy parallel use might need an enterprise plan.
	•	If implementing parallelism, be careful with thread-safety of the ElevenLabs SDK client. It might be safer to initialize a separate client in each thread if needed, or use multiprocessing to avoid Python GIL issues since a lot of time is I/O bound (upload waiting).
	•	However, parallel implementation is complex and could be a future improvement. The PRD will note it, but initial version can be sequential for simplicity.

Memory Management

Processing should be done streaming where possible. For example, reading the entire audio into BytesIO as we do means if an audio file is extremely large (say a 3-hour WAV file, could be ~2 GB), we will allocate that much RAM. This might be a problem. A better approach is if the ElevenLabs SDK or API supports chunked streaming of the upload. It’s not clear if client.speech_to_text.convert can take a generator or if the requests library under the hood streams it. The code suggests reading in chunks and writing to BytesIO explicitly ￼, which is effectively reading fully into memory (just with a progress bar). To handle very large files, we might:
	•	Remove the BytesIO step and stream directly from file to the request. The Python requests library can stream uploads by passing an open file object and using stream=True on the request or chunked transfer encoding ￼ ￼. Stack Overflow discussions show ways to post large files without loading entirely in memory (e.g., using file object in requests.post which streams by default, or using iter_content). The current ElevenLabs SDK likely abstracts this, but we could consider using requests directly if needed. According to one solution, using requests.post(url, data=f) with a file object streams it chunkwise ￼, but the server must support chunked encoding. If the SDK doesn’t handle chunked, we accept the memory hit or document a requirement of sufficient RAM for large files.
	•	In practice, audio files might not be extremely huge in most use cases (many will be under 1 hour, which as MP3 is <100 MB). It’s a tolerable trade-off.

Robustness and Edge Cases
	•	Special Characters in Text: Ensure the system can handle transcripts that contain characters outside ASCII (which is likely for Hebrew transcripts, etc.). All file writing should use UTF-8. All internal string handling in Python 3 is Unicode, so we should be fine as long as we don’t accidentally encode with a wrong codec.
	•	Long audio files: If an audio file is very long (hours), Scribe might take a long time or potentially time out. We should consider if the API has a timeout. The current script just waits, and tqdm shows progress as indeterminate (just spinner). Possibly the API can handle long inputs since it’s designed for batch. If needed, breaking audio into chunks could be a strategy, but that complicates reassembling transcripts, so we avoid unless necessary.
	•	API errors or rate limits: Implement retries for transient errors. If a call fails due to a network glitch, maybe retry once or twice after a short delay. If it consistently fails (maybe due to content or a bug), skip and mark as failed. For rate limiting, if the API returns a rate limit response, implement a backoff (sleep and retry).
	•	User Abortion: If the user presses Ctrl+C, ensure that partial results are saved safely up to that point (maybe flush outputs frequently). This is more runtime behavior than design, but good to note.

Comparisons to Current Script & Better Practices

This enhanced design introduces several improvements over the current single-file script:
	•	Batch & Recursion: Previously only one directory level was handled ￼. We now can handle nested folders and large batches seamlessly.
	•	Multi-language Output: The original script transcribed in one language at a time (user had to specify --language, or use auto) ￼. Our design integrates multiple languages in one run per file. This is a significant functional expansion.
	•	Filename Handling: The current script doesn’t address special characters; it would likely fail or produce oddly named outputs if given weird filenames. We proactively handle sanitization to avoid crashes or misnamed outputs.
	•	Output Management: The original dumps all outputs in one folder, potentially overwriting or mixing files. Our approach to structured output (per file folders) and clear naming is a better practice for managing many output files and preventing name collisions.
	•	Summary Reporting: The original script prints some info per file and that’s it. We add a comprehensive summary, which is crucial for user to get a high-level view after hours of processing. This is a usability improvement.
	•	Efficiency Notes: We embrace some best practices like reusing audio data for multiple API calls, using metadata for durations, and (optionally) using a safer audio extraction method. These reduce redundant work. Another potential improvement we noted is using a direct ffmpeg call for audio extraction to speed it up; this could be implemented if needed (ffmpeg is known for its speed and could cut down extraction time compared to high-level libraries).
	•	Robustness: More careful error handling (not present in original aside from basic try/except around each file) ensures the tool can process dozens of files and not stop entirely on one error.
	•	Extensibility: By structuring the code to handle a list of languages, it’s easy to add or remove languages (e.g., to add French or others) by adjusting a configuration. The PRD’s specific ask is DE/EN/HE, but we keep in mind the general case.

In conclusion, these requirements and considerations form a blueprint for implementing a batch transcription tool that is robust, user-friendly, and capable of producing multi-language transcripts and subtitles at scale. Following these guidelines will result in a significantly more powerful tool compared to the original script, aligning with best practices in file handling and utilizing ElevenLabs Scribe v1’s capabilities to the fullest while compensating for its lack of built-in translation with external solutions. The end result will greatly assist users in transcribing and translating large volumes of audio/video content efficiently.