import os
import sys

def make_reg():
    python_path = sys.executable.replace('\\', '\\\\')
    # Assuming your script is named add_to_steam.py and in the same folder as make_reg.py
    script_path = os.path.abspath("add_to_steam.py").replace('\\', '\\\\')

    reg_content = f"""Windows Registry Editor Version 5.00

[HKEY_CLASSES_ROOT\\exefile\\shell\\AddToSteam]
@="Add to Steam (Non-Steam Game)"

[HKEY_CLASSES_ROOT\\exefile\\shell\\AddToSteam\\command]
@="\\"{python_path}\\" \\"{script_path}\\" \\"%1\\""

[HKEY_CLASSES_ROOT\\lnkfile\\shell\\AddToSteam]
@="Add to Steam (Non-Steam Game)"

[HKEY_CLASSES_ROOT\\lnkfile\\shell\\AddToSteam\\command]
@="\\"{python_path}\\" \\"{script_path}\\" \\"%1\\""
"""

    folder = "C:\\addtosteam"
    os.makedirs(folder, exist_ok=True)
    reg_path = os.path.join(folder, "add_to_steam_context_menu.reg")

    with open(reg_path, "w") as f:
        f.write(reg_content)

    print(f"Registry file created at: {reg_path}")
    print("You can double-click this file to add the context menu entry.")

if __name__ == "__main__":
    make_reg()
