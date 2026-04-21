import os
import subprocess
from typing import Tuple

def check_has_git() -> bool:
    res = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], capture_output=True)
    return res.returncode == 0

def create_worktree(session_name: str) -> Tuple[bool, str, str]:
    """
    Creates a git worktree for the session if we are in a git repository.
    Returns (success, working_directory, error_message)
    """
    work_dir = os.getcwd()
    
    if not check_has_git():
        return False, work_dir, "Not in a git repository."
        
    branch_name = f"agent-{session_name}"
    worktree_dir = os.path.abspath(os.path.join("..", ".ab-worktrees", session_name))
    os.makedirs(os.path.join("..", ".ab-worktrees"), exist_ok=True)
    
    res = subprocess.run(
        ["git", "worktree", "add", "-b", branch_name, worktree_dir],
        capture_output=True, text=True
    )
    
    if res.returncode == 0:
        return True, worktree_dir, ""
    else:
        return False, work_dir, res.stderr

def remove_worktree(session_name: str) -> bool:
    """
    Removes the git worktree for the given session.
    """
    worktree_dir = os.path.abspath(os.path.join("..", ".ab-worktrees", session_name))
    if os.path.exists(worktree_dir):
        res = subprocess.run(["git", "worktree", "remove", worktree_dir, "--force"])
        return res.returncode == 0
    return False
