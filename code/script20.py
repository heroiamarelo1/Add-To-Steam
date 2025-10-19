import os
import sys
import struct
import subprocess
import time
import win32com.client  # pip install pywin32
import vdf              # pip install vdf
import hashlib

# --- GLOBAL CONFIGURATION ---
STEAM_PATH = os.path.expandvars(r"%ProgramFiles(x86)%\Steam\Steam.exe")

# --- PATH & REGISTRY SETUP FUNCTIONS ---

def get_exe_path():
    """Gets the full path to the bundled executable for the .reg file."""
    # sys.executable returns the path to the running EXE when bundled.
    return os.path.abspath(sys.executable).replace("\\", "\\\\")

def get_script_directory():
    """Reliably finds the directory of the running executable/script."""
    if getattr(sys, 'frozen', False):
        # Running as a PyInstaller executable
        return os.path.dirname(sys.executable)
    else:
        # Running as a normal Python script
        return os.path.dirname(os.path.abspath(__file__))

def generate_reg_content(exe_path):
    """Generates the content for the .reg file to create the context menu."""
    return f"""Windows Registry Editor Version 5.00

; Add context menu to .lnk files
[HKEY_CLASSES_ROOT\\lnkfile\\shell\\AddToSteam]
@="Add to Steam Library"

[HKEY_CLASSES_ROOT\\lnkfile\\shell\\AddToSteam\\command]
@="\\"{exe_path}\\" \\"%1\\""

; Add context menu to .exe files
[HKEY_CLASSES_ROOT\\exefile\\shell\\AddToSteam]
@="Add to Steam Library"

[HKEY_CLASSES_ROOT\\exefile\\shell\\AddToSteam\\command]
@="\\"{exe_path}\\" \\"%1\\""
"""

# --- STEAM ADMIN STARTUP LOGIC (Batch Script Generator) ---

def generate_admin_startup_bat():
    """Generates the content for the .bat file to create the elevated Steam startup task."""

    # Escaping percentage signs (%%) for batch file variables is crucial
    bat_content = f"""@echo off
REM ##################################################################
REM # ELEVATED STEAM STARTUP SCRIPT
REM # GOAL: Create a Scheduled Task that launches Steam with
REM #       Administrator privileges upon User Logon.
REM #
REM # WARNING: This file MUST be executed "As Administrator".
REM ##################################################################

set TASK_NAME="Steam Admin Startup"
set STEAM_PATH="{STEAM_PATH}"
set CURRENT_USER=%%USERNAME%%

echo.
echo === PREREQUISITE: DISABLE INTERNAL STARTUP ===
echo.
echo Please ENSURE the option "Run Steam when my computer starts"
echo is UNCHECKED in Steam Settings ^> Interface.
echo.
pause

echo === 1. Checking Steam Path ===
if not exist %STEAM_PATH% (
    echo ERROR: Steam executable not found at:
    echo %STEAM_PATH%
    pause
    exit /b 1
)

echo === 2. Creating Scheduled Task with Highest Privileges ===

schtasks /create /TN %TASK_NAME% /TR %STEAM_PATH% /SC ONLOGON /RU %CURRENT_USER% /RL HIGHEST /F

IF %%ERRORLEVEL%% NEQ 0 (
    echo.
    echo ERROR: Failed to create the scheduled task.
    echo Ensure you ran this file "As Administrator".
) ELSE (
    echo.
    echo SUCCESS! Scheduled Task '%%TASK_NAME%%' has been created and is active.
    echo Steam will now start automatically with Administrator privileges on login.
)

echo.
echo Press any key to exit...
pause > nul
"""

    # Save the .bat file
    output_file = os.path.join(get_script_directory(), "CREATE_STEAM_ADMIN_TASK.bat")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(bat_content.replace("\\\\", "\\"))

    print(f"\nScheduled Task Script '{output_file}' created successfully!")
    print("--------------------------------------------------------------------------------")


# --- MAIN EXECUTION LOGIC (Setup Mode) ---

def generate_reg_main():
    """The main function to generate the .reg file (Setup Mode)."""
    exe_path = get_exe_path()

    print("--------------------------------------------------------------------------------")
    print("SETUP MODE: Generating Registry and Startup Files.")
    print("--------------------------------------------------------------------------------")
    print("Context menu command will point to:")
    print(exe_path.replace("\\\\", "\\"))

    # 1. Generate and save the .reg file (Context Menu)
    reg_content = generate_reg_content(exe_path)
    output_reg_file = os.path.join(get_script_directory(), "add_to_steam_context_menu.reg")
    with open(output_reg_file, "w", encoding="utf-8") as f:
        f.write(reg_content)

    # 2. Generate and save the .bat file (Admin Startup Task)
    generate_admin_startup_bat()

    print(f"\nRegistry file '{output_reg_file}' created successfully!")
    print("\n--- ACTION REQUIRED (1/2): Double-click 'add_to_steam_context_menu.reg' to activate the context menu.")
    print("\n--- ACTION REQUIRED (2/2): Right-click 'CREATE_STEAM_ADMIN_TASK.bat' and select 'Run as administrator'.")
    print("\nNote: If you move this executable, you MUST run this setup again and re-apply the files.")

    os.startfile(get_script_directory())
    input("\nPress Enter to exit...")


# --- STEAM SHORTCUT LOGIC FUNCTIONS (Core Logic) ---

def select_steam_userid():
    userdata_path = os.path.join(os.path.expandvars(r"%ProgramFiles(x86)%\Steam"), "userdata")
    if not os.path.exists(userdata_path):
        print(f"Error: Steam userdata folder not found at:\n{userdata_path}")
        return None

    folders = [f for f in os.listdir(userdata_path) if f.isdigit()]
    if not folders:
        print("No Steam user IDs found in userdata folder.")
        return None
    elif len(folders) == 1:
        print(f"Found single Steam user ID: {folders[0]}")
        return folders[0]
    else:
        print("Multiple Steam user IDs found. Please select one:")
        for idx, folder in enumerate(folders, 1):
            print(f"Press {idx} for ID {folder}")
        while True:
            choice = input("Your choice: ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(folders):
                selected = folders[int(choice) - 1]
                print(f"Selected Steam user ID: {selected}")
                return selected
            else:
                print("Invalid choice, please try again.")

def get_shortcuts_vdf_path(steam_id):
    steam_path = os.path.expandvars(r"%ProgramFiles(x86)%\Steam")
    vdf_path = os.path.join(steam_path, "userdata", steam_id, "config", "shortcuts.vdf")
    if os.path.exists(vdf_path):
        return vdf_path
    else:
        print(f"Error: shortcuts.vdf not found at:\n{vdf_path}")
        return None

def get_shortcut_info(lnk_path):
    """
    Retrieves the target path and any command-line arguments from a .lnk file.
    Returns: (target_path, arguments)
    """
    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortcut(lnk_path)

    # TargetPath is the executable (e.g., C:\Game\game.exe)
    target = shortcut.TargetPath

    # Arguments are the parameters (e.g., -w -fullscreen)
    arguments = shortcut.Arguments

    return target, arguments


def create_entry(exe, name, launch_options=""):
    """
    Creates a dictionary representing a VDF shortcut entry.
    Added 'launch_options' parameter.
    """
    return {
        'appname': name,
        # Quote the executable path only, the launch options are separate
        'exe': f'"{exe}"',
        'StartDir': os.path.dirname(exe),
        'icon': '',
        'ShortcutPath': '',
        'LaunchOptions': launch_options, # Set LaunchOptions here
        'IsHidden': 0,
        'AllowDesktopConfig': 1,
        'AllowOverlay': 1,
        'openvr': 0,
        'tags': {
            '0': 'Non-Steam',
        }
    }

def restart_steam():
    print("Restarting Steam...")
    # Force kill Steam
    subprocess.run(['taskkill', '/IM', 'steam.exe', '/F'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3)
    # Relaunch Steam
    if os.path.exists(STEAM_PATH):
        subprocess.Popen([STEAM_PATH])
        print("Steam restarted successfully.")
    else:
        print(f"Steam executable not found at {STEAM_PATH}. Please check the path.")

def log_history(exe_path, history_path):
    try:
        exe_abspath = os.path.abspath(exe_path) if exe_path else ""
        with open(history_path, "a", encoding="utf-8") as f:
            f.write(f"{exe_abspath}\n")
        print(f"Logged history to: {history_path}")
    except Exception as e:
        print(f"Failed to write history file: {e}")

# --- MAIN EXECUTION LOGIC (The add/remove toggle) ---

def add_remove_shortcut_main(input_path):
    """The main function to add or remove the shortcut (Execution Mode)."""
    input_path = os.path.abspath(input_path)
    if not os.path.exists(input_path):
        print(f"Error: File not found: {input_path}")
        input("Press Enter to exit...")
        return

    script_dir = get_script_directory()
    history_path = os.path.join(script_dir, "history.txt")

    # 1. Determine the target executable path, name, and arguments
    ext = os.path.splitext(input_path)[1].lower()
    launch_args = ""

    if ext == '.lnk':
        exe_path_for_check, launch_args = get_shortcut_info(input_path)
        default_name = os.path.splitext(os.path.basename(input_path))[0]

    elif ext == '.exe':
        exe_path_for_check = os.path.abspath(input_path)
        default_name = os.path.splitext(os.path.basename(input_path))[0]

    else:
        print("Error: Unsupported file type. Please provide a .lnk shortcut or .exe file.")
        input("Press Enter to exit...")
        return

    exe_path_for_check = os.path.abspath(exe_path_for_check)
    print(f"Target Executable: {exe_path_for_check}")
    if launch_args:
        print(f"Detected Launch Arguments: {launch_args}")
    print(f"Default Steam Name: {default_name}")


    # 2. Check for existing shortcut in history (TOGGLE LOGIC)
    if os.path.exists(history_path):
        with open(history_path, "r", encoding="utf-8") as f:
            history = [line.strip() for line in f if line.strip()]

        if exe_path_for_check in history:
            # --- REMOVAL LOGIC ---
            print(f"Found existing shortcut for: {exe_path_for_check}. Running REMOVAL now.")
            steam_id = select_steam_userid()
            if not steam_id:
                return

            vdf_path = get_shortcuts_vdf_path(steam_id)
            if not vdf_path:
                return

            # Read VDF and remove entry
            try:
                with open(vdf_path, "rb") as f:
                    data = vdf.binary_load(f)
            except Exception as e:
                print(f"Error reading shortcuts.vdf: {e}")
                data = {}

            shortcuts = data.get("shortcuts", {})
            new_shortcuts = {}
            idx2 = 0
            for key in shortcuts:
                entry = shortcuts[key]
                entry_exe = entry.get("exe","").strip('"')
                if os.path.abspath(entry_exe) != exe_path_for_check:
                    new_shortcuts[str(idx2)] = entry
                    idx2 += 1
                else:
                    print(f"Removing shortcut: {entry.get('appname', 'Unknown')}")

            data["shortcuts"] = new_shortcuts

            # Write back the modified VDF
            with open(vdf_path, "wb") as f:
                vdf.binary_dump(data, f)

            # Update history file
            history.remove(exe_path_for_check)
            with open(history_path, "w", encoding="utf-8") as f:
                for path in history:
                    f.write(f"{path}\n")

            print(f"Removed shortcut: {exe_path_for_check}")
            restart_steam()
            return

    # 3. If not in history, ADD the shortcut
    print(f"Shortcut NOT found in history. Running ADDITION now.")
    steam_id = select_steam_userid()
    if not steam_id:
        return

    entry = create_entry(exe_path_for_check, default_name, launch_args)

    vdf_path = get_shortcuts_vdf_path(steam_id)
    if not vdf_path:
        print("Could not find Steam shortcuts.vdf.")
        return

    # Create backup
    backup_path = vdf_path + ".bak"
    if not os.path.exists(backup_path):
        with open(vdf_path, "rb") as original, open(backup_path, "wb") as backup:
            backup.write(original.read())

    # Load, append, and dump VDF
    try:
        with open(vdf_path, "rb") as f:
            data = vdf.binary_load(f)
    except Exception:
        data = {}

    shortcuts = data.get("shortcuts", {})
    new_index = str(len(shortcuts))
    shortcuts[new_index] = entry
    data["shortcuts"] = shortcuts

    with open(vdf_path, "wb") as f:
        vdf.binary_dump(data, f)

    print(f"Added '{default_name}' to Steam non-Steam games.")
    log_history(exe_path_for_check, history_path)

    restart_steam()


if __name__ == "__main__":
    try:
        # Check if the script was run with 1 argument (the path to the file to add)
        if len(sys.argv) == 2:
            add_remove_shortcut_main(sys.argv[1])
        # Check if the script was run with NO arguments (Setup Mode)
        elif len(sys.argv) == 1:
            generate_reg_main()
        # Handle incorrect usage
        else:
            print("Usage: steam_shortcut_tool.exe <shortcut.lnk or .exe> OR run with no arguments to generate the .reg file.")
            input("Press Enter to exit...")
    except Exception as e:
        print("An unexpected error occurred:")
        print(e)
        input("Press Enter to exit...")
