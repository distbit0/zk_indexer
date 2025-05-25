import json
from pathlib import Path
import os
import re
from loguru import logger

# CONFIG_FILE = Path("../config.json").resolve() # Assuming main.py is in src/
CONFIG_FILE = Path(__file__).resolve().parent.parent / "config.json"

def _normalize_text_for_linking(text: str) -> str:
    """Converts text to lowercase and replaces non-alphanumeric chars with spaces."""
    # Convert to lowercase
    text = text.lower()
    # Replace non-alphanumeric characters (and sequences of them) with a single space
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    # Strip leading/trailing spaces that might result from the replacement
    return text.strip()

def load_zettelkasten_path() -> Path | None:
    """Loads the Zettelkasten folder path from config.json."""
    try:
        if not CONFIG_FILE.exists():
            logger.error(f"Configuration file not found: {CONFIG_FILE}")
            return None
        with open(CONFIG_FILE, "r") as f:
            config_data = json.load(f)
        zettelkasten_path_str = config_data.get("zettelkasten_folder_path")
        if not zettelkasten_path_str:
            logger.error(f"'zettelkasten_folder_path' not found in {CONFIG_FILE}")
            return None
        
        z_path = Path(zettelkasten_path_str)
        if not z_path.exists():
            logger.error(f"Zettelkasten path does not exist: {z_path}")
            logger.info(f"Please update 'zettelkasten_folder_path' in {CONFIG_FILE}")
            return None
        if not z_path.is_dir():
            logger.error(f"Zettelkasten path is not a directory: {z_path}")
            return None
            
        logger.info(f"Successfully loaded Zettelkasten path: {z_path}")
        return z_path
    except json.JSONDecodeError:
        logger.error(f"Error decoding JSON from {CONFIG_FILE}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while loading config: {e}")
        return None

def list_md_files_in_zettelkasten(zettelkasten_path: Path) -> list[Path]:
    """Lists all .md files in the Zettelkasten folder (non-recursive)."""
    if not zettelkasten_path or not zettelkasten_path.is_dir():
        logger.error(f"Invalid Zettelkasten path provided: {zettelkasten_path}")
        return []

    md_files = []
    try:
        for item in zettelkasten_path.iterdir():
            if item.is_file() and item.suffix.lower() == ".md":
                md_files.append(item)
        
        if not md_files:
            logger.info(f"No .md files found in {zettelkasten_path}")
        else:
            logger.info(f"Found {len(md_files)} .md file(s) in {zettelkasten_path}")
        return md_files
    except Exception as e:
        logger.error(f"Error listing .md files in {zettelkasten_path}: {e}")
        return []

def extract_wikilinks_from_content(content_str: str) -> set[str]:
    """Extracts all unique, normalized wikilinks from a string of markdown content."""
    # Regex to find [[wikilinks]]
    # It captures the content inside the brackets
    wikilink_pattern = r'\[\[([^\]]+)\]\]'
    found_links = re.findall(wikilink_pattern, content_str)
    
    normalized_links = set()
    for link_target in found_links:
        # Normalize the link target using the new common normalization function
        normalized_links.add(_normalize_text_for_linking(link_target.strip()))
        
    return normalized_links

# --- Refactored Helper Functions ---

def _collect_note_and_index_data(md_files: list[Path]) -> tuple[dict[str, str], list[Path], set[str]]:
    """Collects all note data, identifies index files, and returns normalized note names."""
    all_notes_data: dict[str, str] = {}
    index_file_paths: list[Path] = []

    for f in md_files:
        original_stem = f.stem  # e.g., "My Note Title"
        normalized_name = _normalize_text_for_linking(original_stem)  # e.g., "my note title"
        
        if normalized_name in all_notes_data:
            logger.warning(f"Duplicate normalized note name '{normalized_name}' detected. Original stems: '{all_notes_data[normalized_name]}' and '{original_stem}'. Using the first one encountered: '{all_notes_data[normalized_name]}'.")
        else:
            all_notes_data[normalized_name] = original_stem

        if f.name.lower().endswith("index.md"):
            index_file_paths.append(f)
            
    all_normalized_note_names_set = set(all_notes_data.keys())
    
    logger.info(f"Found {len(all_normalized_note_names_set)} unique normalized note name(s).")
    logger.debug(f"All notes data (normalized -> original stem): {all_notes_data}")
    logger.info(f"Found {len(index_file_paths)} index file(s): {[f.name for f in index_file_paths]}")
    
    return all_notes_data, index_file_paths, all_normalized_note_names_set

def _extract_all_wikilinks_from_indices(index_file_paths: list[Path]) -> set[str]:
    """Extracts all unique, normalized wikilinks from a list of index files."""
    notes_linked_from_indices: set[str] = set()
    if not index_file_paths:
        logger.info("No index files found to process for links.")
        return notes_linked_from_indices

    for index_file_path in index_file_paths:
        try:
            content = index_file_path.read_text(encoding='utf-8')
            linked_notes = extract_wikilinks_from_content(content)
            logger.debug(f"Links found in {index_file_path.name}: {linked_notes}")
            notes_linked_from_indices.update(linked_notes)
        except Exception as e:
            logger.error(f"Error reading or processing index file {index_file_path.name}: {e}")
            
    logger.info(f"Found {len(notes_linked_from_indices)} unique notes linked from all index files.")
    logger.debug(f"All notes linked from indices (normalized): {notes_linked_from_indices}")
    return notes_linked_from_indices

def _determine_unindexed_notes(all_normalized_note_names: set[str], linked_notes_normalized: set[str]) -> set[str]:
    """Determines the set of normalized note names that are unindexed."""
    if not all_normalized_note_names:
        logger.info("No notes available to determine unindexed ones.")
        return set()
        
    notes_for_unindexed_md = all_normalized_note_names - linked_notes_normalized
    logger.info(f"{len(notes_for_unindexed_md)} candidate(s) for unindexed.md before filtering 'unindexed' itself.")

    normalized_unindexed_filename = _normalize_text_for_linking("unindexed")
    if normalized_unindexed_filename in notes_for_unindexed_md:
        notes_for_unindexed_md.remove(normalized_unindexed_filename)
        logger.info(f"Removed '{normalized_unindexed_filename}' (normalized 'unindexed') from the list of notes for unindexed.md.")
    
    logger.info(f"{len(notes_for_unindexed_md)} note(s) determined to be unindexed.")
    return notes_for_unindexed_md

def _parse_existing_unindexed_file(unindexed_md_path: Path, current_unindexed_normalized: set[str]) -> tuple[list[str], set[str], bool]:
    """Reads existing unindexed.md, preserves relevant lines and non-note content."""
    preserved_lines: list[str] = []
    kept_normalized_notes: set[str] = set()
    file_had_removals = False

    if not unindexed_md_path.exists():
        logger.debug(f"{unindexed_md_path.name} does not exist. No existing content to parse.")
        return preserved_lines, kept_normalized_notes, file_had_removals

    logger.debug(f"Reading existing {unindexed_md_path.name} to preserve content.")
    try:
        existing_lines = unindexed_md_path.read_text(encoding='utf-8').splitlines()
        for line_num, line_content in enumerate(existing_lines):
            match = re.fullmatch(r'\s*\[\[\s*([^]]+?)\s*\]\]\s*', line_content)
            if match:
                original_text_in_link = match.group(1).strip()
                note_name_in_line_normalized = _normalize_text_for_linking(original_text_in_link)
                
                if note_name_in_line_normalized in current_unindexed_normalized:
                    preserved_lines.append(line_content)
                    kept_normalized_notes.add(note_name_in_line_normalized)
                    logger.debug(f"Keeping line {line_num+1} (normalized: '{note_name_in_line_normalized}', original: '{original_text_in_link}') from {unindexed_md_path.name}: '{line_content}'")
                else:
                    logger.info(f"Note (normalized: '{note_name_in_line_normalized}', original: '{original_text_in_link}') from line {line_num+1} of {unindexed_md_path.name} ('{line_content}') is no longer unindexed. Removing this line.")
                    file_had_removals = True
            else:
                preserved_lines.append(line_content)
                logger.debug(f"Preserving non-note line {line_num+1} from {unindexed_md_path.name}: '{line_content}'")
    except Exception as e:
        logger.error(f"Error reading or parsing {unindexed_md_path.name}: {e}. Assuming no lines preserved.")
        return [], set(), True # Assume change as we can't preserve
    
    return preserved_lines, kept_normalized_notes, file_had_removals

def _prepare_final_unindexed_content(
    preserved_lines: list[str], 
    kept_normalized_notes: set[str], 
    current_unindexed_normalized: set[str], 
    all_notes_data: dict[str, str]
) -> tuple[list[str], bool]:
    """Prepares the final list of lines for unindexed.md, adding new notes."""
    final_content_lines = list(preserved_lines) # Start with a copy
    file_had_additions = False

    newly_unindexed_to_add_normalized = sorted(list(current_unindexed_normalized - kept_normalized_notes))

    if newly_unindexed_to_add_normalized:
        logger.info(f"Adding {len(newly_unindexed_to_add_normalized)} new unindexed note(s).")
        file_had_additions = True
        for normalized_note_name_to_add in newly_unindexed_to_add_normalized:
            original_stem_to_link = all_notes_data.get(normalized_note_name_to_add)
            if original_stem_to_link:
                new_line_to_add = f"[[{original_stem_to_link}]]"
                final_content_lines.append(new_line_to_add)
                logger.debug(f"Appending new unindexed note (normalized: '{normalized_note_name_to_add}', original: '{original_stem_to_link}') to content: {new_line_to_add}")
            else:
                logger.error(f"Could not find original stem for normalized note name '{normalized_note_name_to_add}'. Skipping addition.")
    
    return final_content_lines, file_had_additions

def _write_unindexed_md_if_needed(
    unindexed_md_path: Path, 
    final_content_lines: list[str], 
    initial_file_existed: bool,
    file_had_removals: bool, 
    file_had_additions: bool
):
    """Writes the final content to unindexed.md if changes were made or file is new."""
    # Determine if a write is potentially needed
    # A write is needed if: file is new and has content, or file existed and had additions/removals.
    potential_write_needed = (not initial_file_existed and final_content_lines) or \
                             (initial_file_existed and (file_had_additions or file_had_removals))

    # Prepare final string content
    # Clean up trailing empty lines
    processed_lines = list(final_content_lines)
    while processed_lines and processed_lines[-1].strip() == "":
        processed_lines.pop()
    # Add a single newline at the end if there's content
    if processed_lines:
        processed_lines.append("")
    new_content_str = "\n".join(processed_lines)

    # If the file existed, we need to compare with its original content to be absolutely sure a change occurred,
    # especially if only non-wikilink lines were present or formatting changes are the only difference.
    actual_change_occurred = False
    if initial_file_existed:
        try:
            original_file_content = unindexed_md_path.read_text(encoding='utf-8')
            if original_file_content != new_content_str:
                actual_change_occurred = True
                logger.info(f"Content of {unindexed_md_path.name} has changed. Update needed.")
            else:
                # Even if additions/removals were flagged, if final content is same, no actual change
                logger.info(f"No effective changes to content of {unindexed_md_path.name} after processing. File not written.")
        except Exception as e:
            logger.warning(f"Could not re-read {unindexed_md_path.name} for final comparison: {e}. Assuming change if write was potentially needed.")
            actual_change_occurred = potential_write_needed # Be cautious
    elif final_content_lines: # File did not exist, but now we have content for it
        actual_change_occurred = True
        logger.info(f"{unindexed_md_path.name} will be created with new content.")
    
    if actual_change_occurred:
        try:
            unindexed_md_path.write_text(new_content_str, encoding='utf-8')
            logger.info(f"Successfully wrote/updated {unindexed_md_path.name}.")
        except Exception as e:
            logger.error(f"Error writing to {unindexed_md_path.name}: {e}")
    elif not initial_file_existed and not final_content_lines:
        logger.info(f"{unindexed_md_path.name} does not exist and no unindexed notes to add. File not created.")
    elif initial_file_existed and not actual_change_occurred:
        # This case is covered by the logger message inside the 'if initial_file_existed:' block
        pass 


def _update_unindexed_md_file(unindexed_md_path: Path, current_unindexed_normalized: set[str], all_notes_data: dict[str, str]):
    """Coordinates the update of the unindexed.md file."""
    initial_file_existed = unindexed_md_path.exists()

    preserved_lines, kept_normalized_notes, file_had_removals = \
        _parse_existing_unindexed_file(unindexed_md_path, current_unindexed_normalized)

    final_content_lines, file_had_additions = \
        _prepare_final_unindexed_content(preserved_lines, kept_normalized_notes, current_unindexed_normalized, all_notes_data)
    
    _write_unindexed_md_if_needed(
        unindexed_md_path, 
        final_content_lines, 
        initial_file_existed, 
        file_had_removals, 
        file_had_additions
    )


def _ensure_index_file_tags(index_file_paths: list[Path], tag_to_ensure: str = "#index"):
    """Ensures all specified index files contain the given tag."""
    if not index_file_paths:
        logger.info("No index files found to tag.")
        return

    logger.info(f"Starting Phase: Tagging index files with '{tag_to_ensure}'.")
    for index_file_path in index_file_paths:
        try:
            original_content = index_file_path.read_text(encoding='utf-8')
            if tag_to_ensure not in original_content:
                logger.info(f"Tagging {index_file_path.name} with {tag_to_ensure}.")
                
                content_lines = original_content.splitlines(True) # Keep line endings
                frontmatter_end_line_index = -1
                if content_lines and content_lines[0].strip() == "---":
                    for i, line in enumerate(content_lines[1:], start=1):
                        if line.strip() == "---":
                            frontmatter_end_line_index = i
                            break
                
                processed_lines = []
                # Ensure tag has a newline if it's not the only content or part of frontmatter
                tag_line = f"{tag_to_ensure}\n"

                if frontmatter_end_line_index != -1:
                    processed_lines.extend(content_lines[:frontmatter_end_line_index + 1])
                    # Check if line after frontmatter is blank, if so, can use it
                    if frontmatter_end_line_index + 1 < len(content_lines) and content_lines[frontmatter_end_line_index + 1].strip() == "":
                        processed_lines.append(tag_line) # Add tag
                        processed_lines.extend(content_lines[frontmatter_end_line_index + 2:]) # Skip the blank line
                    else:
                        processed_lines.append(tag_line) # Add tag
                        if frontmatter_end_line_index + 1 < len(content_lines):
                             processed_lines.extend(content_lines[frontmatter_end_line_index + 1:])
                else:
                    # No valid frontmatter. Add tag, then a blank line if content exists, then content.
                    processed_lines.append(tag_line)
                    if content_lines and content_lines[0].strip() != "": # If first line had content
                        if not content_lines[0].startswith("\n") and tag_line.endswith("\n") : # ensure separation if needed
                             pass # tag_line already ends with \n
                    processed_lines.extend(content_lines)
                
                new_content_str = "".join(processed_lines).rstrip() + "\n" # Ensure single trailing newline

                if new_content_str != original_content:
                    index_file_path.write_text(new_content_str, encoding='utf-8')
                    logger.info(f"Successfully tagged {index_file_path.name}.")
                else:
                    logger.debug(f"Content for {index_file_path.name} with {tag_to_ensure} tag resulted in no effective change. Skipping write.")
            else:
                logger.debug(f"{index_file_path.name} already contains the {tag_to_ensure} tag.")
        except Exception as e:
            logger.error(f"Error processing or tagging index file {index_file_path.name}: {e}")


def main():
    zk_path = load_zettelkasten_path()
    if not zk_path:
        logger.error("Failed to load Zettelkasten path. Exiting.")
        return

    md_files = list_md_files_in_zettelkasten(zk_path)
    if not md_files:
        logger.info("No .md files found in the Zettelkasten. Skipping further processing.")
        return

    logger.info(f"Proceeding with Zettelkasten at: {zk_path}")

    # Phase 1: Collect all note data and identify index files
    logger.info("Starting Phase 1: Collecting note and index data.")
    all_notes_data, index_file_paths, all_normalized_note_names_set = _collect_note_and_index_data(md_files)
    if not all_normalized_note_names_set:
        logger.info("No processable notes found after initial collection. Exiting.")
        return

    # Phase 2: Extract all links from index files
    logger.info("Starting Phase 2: Extracting links from index files.")
    notes_linked_from_indices_normalized = _extract_all_wikilinks_from_indices(index_file_paths)

    # Phase 3: Determine unindexed notes and update unindexed.md
    logger.info("Starting Phase 3: Determining unindexed notes and updating unindexed.md.")
    unindexed_notes_normalized = _determine_unindexed_notes(all_normalized_note_names_set, notes_linked_from_indices_normalized)
    unindexed_md_path = zk_path / "unindexed.md"
    _update_unindexed_md_file(unindexed_md_path, unindexed_notes_normalized, all_notes_data)

    # Phase 4: Ensure index files are tagged
    logger.info("Starting Phase 4: Tagging index files.") # Log for this phase was in _ensure_index_file_tags
    _ensure_index_file_tags(index_file_paths) # Default tag is "#index"

    logger.info("Zettelkasten Indexer Script finished successfully.")


if __name__ == "__main__":
    # Initialize logger
    logger.remove() # Remove default handler
    logger.add(lambda msg: print(msg, end=''), format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}") # Basic console logger
    logger.add("debug.log", rotation="10 MB", level="DEBUG") # Log to a file
    logger.info("Starting Zettelkasten Indexer Script")
    main()
