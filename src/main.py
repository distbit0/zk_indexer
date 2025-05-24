import json
from pathlib import Path
import os
import re
from loguru import logger

# CONFIG_FILE = Path("../config.json").resolve() # Assuming main.py is in src/
CONFIG_FILE = Path(__file__).resolve().parent.parent / "config.json"

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

def normalize_note_name(filename_str: str) -> str:
    """Normalizes a note filename by removing .md extension if present."""
    name, ext = os.path.splitext(filename_str)
    if ext.lower() == ".md":
        return name
    return filename_str

def extract_wikilinks_from_content(content_str: str) -> set[str]:
    """Extracts all unique, normalized wikilinks from a string of markdown content."""
    # Regex to find [[wikilinks]]
    # It captures the content inside the brackets
    wikilink_pattern = r'\[\[([^\]]+)\]\]'
    found_links = re.findall(wikilink_pattern, content_str)
    
    normalized_links = set()
    for link_target in found_links:
        # Normalize the link target (e.g., remove .md, handle potential paths if necessary later)
        # For now, basic normalization as per normalize_note_name
        normalized_links.add(normalize_note_name(link_target.strip()))
        
    return normalized_links

def main():
    # logger.info("Starting the application") # Redundant, already logged in __main__
    zk_path = load_zettelkasten_path()
    if zk_path:
        logger.info(f"Proceeding with Zettelkasten at: {zk_path}")
        md_files = list_md_files_in_zettelkasten(zk_path)
        if md_files:
            logger.debug(f"MD files found: {[str(f) for f in md_files]}")
            
            all_note_names = {normalize_note_name(f.name) for f in md_files}
            logger.info(f"Found {len(all_note_names)} unique note name(s).")
            logger.debug(f"All note names: {all_note_names}")

            index_file_paths = [f for f in md_files if f.name.lower().endswith("index.md")]
            logger.info(f"Found {len(index_file_paths)} index file(s): {[f.name for f in index_file_paths]}")

            notes_linked_from_indices: set[str] = set()
            if index_file_paths:
                for index_file_path in index_file_paths:
                    try:
                        content = index_file_path.read_text(encoding='utf-8')
                        linked_notes = extract_wikilinks_from_content(content)
                        logger.debug(f"Links found in {index_file_path.name}: {linked_notes}")
                        notes_linked_from_indices.update(linked_notes)
                    except Exception as e:
                        logger.error(f"Error reading or processing index file {index_file_path}: {e}")
                logger.info(f"Found {len(notes_linked_from_indices)} unique notes linked from index files.")
                logger.debug(f"Notes linked from indices: {notes_linked_from_indices}")
            else:
                logger.info("No index files found to process for links.")

            # Calculate notes for unindexed.md
            if all_note_names: # Ensure all_note_names is not None (it's a set, so it can be empty but not None)
                notes_for_unindexed_md = all_note_names - notes_linked_from_indices
                logger.info(f"{len(notes_for_unindexed_md)} notes candidates for unindexed.md before filtering 'unindexed'.")

                # Remove "unindexed" from the set if present
                if "unindexed" in notes_for_unindexed_md:
                    notes_for_unindexed_md.remove("unindexed")
                    logger.info("Removed 'unindexed' from the list of notes for unindexed.md.")
                
                sorted_notes_for_unindexed = sorted(list(notes_for_unindexed_md))
                logger.info(f"Found {len(sorted_notes_for_unindexed)} notes to list in unindexed.md.")
                logger.debug(f"Notes for unindexed.md: {sorted_notes_for_unindexed}")

                # Construct content for unindexed.md
                unindexed_content = "\n".join([f"[[{name}]]" for name in sorted_notes_for_unindexed])
                
                unindexed_md_path = zk_path / "unindexed.md"
                try:
                    write_needed = False 
                    if unindexed_md_path.exists():
                        current_content_on_disk = unindexed_md_path.read_text(encoding='utf-8')
                        if current_content_on_disk != unindexed_content:
                            write_needed = True
                    else: # File does not exist, so needs to be written
                        write_needed = True
                    
                    if write_needed:
                        unindexed_md_path.write_text(unindexed_content, encoding='utf-8')
                        logger.info(f"Successfully wrote/updated {unindexed_md_path}")
                    else:
                        logger.info(f"Content of {unindexed_md_path} is already up-to-date. No write needed.")
                except Exception as e:
                    logger.error(f"Error processing {unindexed_md_path}: {e}")
            else:
                logger.info("No notes found in the Zettelkasten to process for unindexed.md.")

            # Phase 4: Tagging Index Files
            if index_file_paths:
                logger.info("Starting Phase 4: Tagging index files.")
                for index_file_path in index_file_paths:
                    try:
                        original_content = index_file_path.read_text(encoding='utf-8')
                        # New logic for adding #index tag
                        if not "#index" in original_content: 
                            logger.info(f"Tagging {index_file_path.name} with #index.")
                            
                            content_lines = original_content.splitlines(True) # Keep line endings
                            
                            frontmatter_end_line_index = -1
                            # Check for frontmatter (starts with --- and has a closing ---)
                            if content_lines and content_lines[0].strip() == "---":
                                for i, line in enumerate(content_lines[1:], start=1):
                                    if line.strip() == "---":
                                        frontmatter_end_line_index = i
                                        break
                            
                            processed_lines = []
                            tag_to_add = "#index\n"

                            if frontmatter_end_line_index != -1:
                                # Insert #index after frontmatter
                                processed_lines.extend(content_lines[:frontmatter_end_line_index + 1])
                                processed_lines.append(tag_to_add)
                                if frontmatter_end_line_index + 1 < len(content_lines):
                                    processed_lines.extend(content_lines[frontmatter_end_line_index + 1:])
                            else:
                                # No valid frontmatter found, or no frontmatter at all. Insert at the beginning.
                                processed_lines.append(tag_to_add)
                                processed_lines.extend(content_lines) # Add original content after the tag
                            
                            new_content_str = "".join(processed_lines)
                            if new_content_str != original_content:
                                index_file_path.write_text(new_content_str, encoding='utf-8')
                                logger.info(f"Successfully tagged {index_file_path.name}.")
                            else:
                                # This case should ideally not be hit if the #index check is correct and leads to a change
                                logger.debug(f"Content for {index_file_path.name} with #index tag resulted in no change. Skipping write.")
                        else:
                            logger.debug(f"{index_file_path.name} already contains the #index tag.")
                    except Exception as e:
                        logger.error(f"Error processing or tagging index file {index_file_path}: {e}")
            else:
                logger.info("No index files found to tag.")

        else: # if not md_files
            logger.info("No .md files found in the Zettelkasten. Skipping unindexed.md generation and index tagging.")

    else:
        logger.error("Failed to load Zettelkasten path. Exiting.")


if __name__ == "__main__":
    # Initialize logger
    logger.remove() # Remove default handler
    logger.add(lambda msg: print(msg, end=''), format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}") # Basic console logger
    logger.add("debug.log", rotation="10 MB", level="DEBUG") # Log to a file
    logger.info("Starting Zettelkasten Indexer Script")
    main()
