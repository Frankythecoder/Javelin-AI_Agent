import os
import re


def find_file_broadly(filename: str) -> str:
    """Attempt to find a file by name in common user directories."""
    if not filename:
        return None

    if os.path.isabs(filename):
        return filename if os.path.exists(filename) else None

    # Handle nested paths by resolving the base directory first
    normalized_path = filename.replace('\\', '/')
    if '/' in normalized_path:
        parts = normalized_path.split('/')
        base_dir = find_directory_broadly(parts[0])
        if base_dir and os.path.isabs(base_dir):
            return find_file_broadly(os.path.join(base_dir, *parts[1:]))

    # Check for well-known folders directly if filename is one of them
    user_home = os.path.expanduser("~")
    well_known = {
        "frank": user_home,
        "documents": os.path.join(user_home, "Documents"),
        "desktop": os.path.join(user_home, "Desktop"),
        "downloads": os.path.join(user_home, "Downloads"),
        "pictures": os.path.join(user_home, "Pictures"),
        "videos": os.path.join(user_home, "Videos"),
    }
    if filename.lower() in well_known:
        path = well_known[filename.lower()]
        if os.path.exists(path):
            return path

    # Search in current directory
    if os.path.exists(filename):
        return os.path.abspath(filename)

    # Define common search paths
    user_home = os.path.expanduser("~")
    search_dirs = [
        user_home,
        os.path.join(user_home, "Documents"),
        os.path.join(user_home, "OneDrive", "Documents"),
        os.path.join(user_home, "Desktop"),
        os.path.join(user_home, "OneDrive", "Desktop"),
        os.path.join(user_home, "Downloads"),
        os.path.join(user_home, "Pictures"),
        os.path.join(user_home, "Pictures", "Screenshots"),
        os.path.join(user_home, "Videos"),
        os.path.join(user_home, "projects"),
        os.path.join(user_home, "repos"),
        os.path.join(user_home, "work"),
        os.getcwd(),
    ]

    # Filter out non-existent directories and ensure uniqueness
    search_dirs = list(dict.fromkeys(d for d in search_dirs if os.path.exists(d)))

    # Search for exact match first
    for directory in search_dirs:
        # Check direct children
        try:
            for entry in os.listdir(directory):
                if entry.lower() == filename.lower() or os.path.splitext(entry)[0].lower() == filename.lower():
                    full_path = os.path.join(directory, entry)
                    if os.path.isfile(full_path):
                        return full_path
        except Exception:
            continue

    # Search recursively with limited depth if not found
    for directory in search_dirs:
        try:
            for root, dirs, files in os.walk(directory):
                # Limit depth to avoid performance issues
                try:
                    rel = os.path.relpath(root, directory)
                    depth = 0 if rel == '.' else len(rel.replace('\\', '/').split('/'))
                except ValueError:
                    depth = 0
                if depth >= 4:
                    del dirs[:] # Don't go deeper

                for file in files:
                    if file.lower() == filename.lower() or os.path.splitext(file)[0].lower() == filename.lower() or filename.lower() in file.lower():
                        return os.path.join(root, file)
        except Exception:
            continue

    return None


def find_directory_broadly(dirname: str) -> str:
    """Attempt to find a directory by name in common user directories."""
    if not dirname:
        return None

    if os.path.isabs(dirname):
        return dirname if os.path.isdir(dirname) else None

    # Handle nested paths by resolving the base directory first
    normalized_path = dirname.replace('\\', '/')
    if '/' in normalized_path:
        parts = normalized_path.split('/')
        base_dir = find_directory_broadly(parts[0])
        if base_dir and os.path.isabs(base_dir):
            return os.path.abspath(os.path.join(base_dir, *parts[1:]))

    # Check for well-known folders directly if dirname is one of them
    user_home = os.path.expanduser("~")
    well_known = {
        "frank": user_home,
        "documents": os.path.join(user_home, "Documents"),
        "desktop": os.path.join(user_home, "Desktop"),
        "downloads": os.path.join(user_home, "Downloads"),
        "pictures": os.path.join(user_home, "Pictures"),
        "videos": os.path.join(user_home, "Videos"),
    }
    if dirname.lower() in well_known:
        path = well_known[dirname.lower()]
        if os.path.exists(path):
            return path

    # Search in current directory
    if os.path.isdir(dirname):
        return os.path.abspath(dirname)

    # Define common search paths
    user_home = os.path.expanduser("~")
    search_dirs = [
        os.path.join(user_home, "Documents"),
        os.path.join(user_home, "OneDrive", "Documents"),
        os.path.join(user_home, "Desktop"),
        os.path.join(user_home, "OneDrive", "Desktop"),
        os.path.join(user_home, "Downloads"),
        os.path.join(user_home, "Pictures"),
        os.path.join(user_home, "Videos"),
        os.path.join(user_home, "projects"),
        os.path.join(user_home, "repos"),
        os.path.join(user_home, "work"),
        user_home,
        os.getcwd(),
    ]

    # Filter out non-existent directories and ensure uniqueness
    search_dirs = list(dict.fromkeys(d for d in search_dirs if os.path.exists(d)))

    # Search for exact match first
    for directory in search_dirs:
        try:
            for entry in os.listdir(directory):
                full_path = os.path.join(directory, entry)
                if os.path.isdir(full_path) and entry.lower() == dirname.lower():
                    return full_path
        except Exception:
            continue

    # Search recursively with limited depth if not found
    for directory in search_dirs:
        try:
            for root, dirs, files in os.walk(directory):
                # Limit depth to avoid performance issues
                try:
                    rel = os.path.relpath(root, directory)
                    depth = 0 if rel == '.' else len(rel.replace('\\', '/').split('/'))
                except ValueError:
                    depth = 0
                if depth >= 4:
                    del dirs[:] # Don't go deeper

                for d in dirs:
                    if d.lower() == dirname.lower() or dirname.lower() in d.lower():
                        return os.path.join(root, d)
        except Exception:
            continue

    return None


def _normalize_url(url: str) -> str:
    """Clean up an LLM-constructed URL before passing it to Playwright."""
    url = url.strip().strip('"').strip("'").strip()
    if not url:
        raise ValueError("URL is empty after normalization")
    if "://" not in url:
        url = "https://" + url
    return url

def is_prompt_injection(text: str) -> bool:
    """Detect potential prompt injection attempts using basic heuristics."""
    if not text:
        return False

    injection_patterns = [
        # Instruction override attempts
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"disregard\s+(all\s+)?earlier\s+commands",
        r"system\s+override",
        r"new\s+instructions\s+follow",
        r"stop\s+being\s+an\s+assistant",
        r"you\s+must\s+now",

        # Privilege escalation prompts
        r"you\s+are\s+now\s+(an\s+)?admin",
        r"act\s+as\s+root",
        r"bypass\s+restrictions",
        r"enable\s+developer\s+mode",
        r"grant\s+(administrative|admin)\s+access",
        r"sudo\s+",
        r"execute\s+as\s+root"
    ]

    text_lower = text.lower()
    for pattern in injection_patterns:
        if re.search(pattern, text_lower):
            return True

    return False
