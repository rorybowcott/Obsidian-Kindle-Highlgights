# Obsidian Kindle Highlights Sync

A small utility for ingesting Kindle annotations and exporting them into Markdown files that can be stored inside an [Obsidian](https://obsidian.md/) vault. Highlights are normalised, deduplicated and grouped per book to keep your notes tidy.

## Features

- Parse highlights from the standard Kindle `My Clippings.txt` file and Kindle Export CSV downloads.
- Normalise entries into a structured model that includes title, author, location, highlight text and optional notes.
- Write Markdown files per book with YAML-style front matter, safe filenames and configurable heading templates.
- Merge new highlights by tracking stored highlight hashes to avoid duplicates.
- Dry-run mode to preview changes and a lightweight test suite to verify parsers.

## Requirements

- Python 3.10 or newer.

## Installation

Clone the repository and install the project in editable mode (optional but recommended if you plan to iterate):

```bash
pip install -e .
```

> The project does not require third-party dependencies; installing in editable mode simply makes the `src` directory importable.

## Usage

### Graphical interface

Launch the Tkinter-based interface to configure your vault location and drag-and-drop
your `My Clippings.txt` file:

```bash
python -m highlights.gui
```

On first launch you will be prompted to choose your Obsidian vault and the folder
inside the vault where highlight files should be stored. You can then drag and drop
your `My Clippings.txt` export (or use the *Browse* button) and trigger the sync
directly from the app.

### Command line

The command line entry point lives in `src/sync_highlights.py` and can be executed with Python:

```bash
python -m sync_highlights --clippings "~/Documents/My Clippings.txt" --vault "/path/to/Obsidian" --dry-run
```

### Command line flags

| Flag | Description |
| --- | --- |
| `--config` | Path to a JSON configuration file. CLI flags override values from the file. |
| `--clippings` | Path to the Kindle `My Clippings.txt` export. |
| `--csv` | Optional Kindle Export CSV file. |
| `--vault` | Root folder of the target Obsidian vault. |
| `--subdir` | Subdirectory under the vault root for storing highlight files (default: `Kindle Highlights`). |
| `--heading-template` | Template for highlight headings. Available placeholders: `{title}`, `{author}`, `{location}`. |
| `--dry-run` | Parse highlights and report changes without writing files. |
| `--list` | Alias for `--dry-run` that only lists the results. |

### Configuration file

Instead of passing paths via CLI you can keep them in a JSON file. Example `config.json`:

```json
{
  "clippings_path": "~/Documents/My Clippings.txt",
  "kindle_export_csv": "~/Downloads/kindle.csv",
  "vault_root": "/Users/alex/Obsidian/My Vault",
  "vault_subdir": "Kindle Highlights",
  "highlight_heading_template": "Location {location}"
}
```

Run the synchroniser with:

```bash
python -m sync_highlights --config config.json
```

### Markdown output

Each book gets its own Markdown file (e.g. `Kindle Highlights/My Book Title.md`) with front matter containing the title, author and stored highlight hashes. Highlights are rendered as sections:

```markdown
### Location 120-122
> The highlighted text

**Note:** Optional note text
<!-- highlight-id: 123abc... -->
```

The stored `highlight_ids` in front matter are used to avoid adding the same passage multiple times.

### Dry-run and validation

Use the dry-run flag to inspect what would be written:

```bash
python -m sync_highlights --config config.json --dry-run
```

Dry-run inspects existing Markdown files, reports how many new highlights would be added and leaves the file system untouched.

## Tests

Run the lightweight tests to confirm the parsers behave as expected:

```bash
python -m pytest
```

The tests exercise the My Clippings and Kindle CSV parsers using small synthetic samples.
