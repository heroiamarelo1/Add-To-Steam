def main(input_path):
    input_path = os.path.abspath(input_path)

    if input_path.lower().endswith('.lnk'):
        print(f"Processing shortcut: {input_path}")
        exe = get_shortcut_target(input_path)
        if not exe or not os.path.exists(exe):
            print(f"Error: Target executable of shortcut not found or invalid: {exe}")
            input("Press Enter to exit...")
            return
    elif input_path.lower().endswith('.exe'):
        print(f"Processing executable: {input_path}")
        exe = input_path
        if not os.path.exists(exe):
            print(f"Error: Executable file not found: {exe}")
            input("Press Enter to exit...")
            return
    else:
        print("Error: Input file must be a .lnk shortcut or a .exe executable.")
        input("Press Enter to exit...")
        return

    steam_id = select_steam_userid()
    if not steam_id:
        input("Press Enter to exit...")
        return

    default_name = os.path.splitext(os.path.basename(exe))[0]
    print(f"Default name is '{default_name}'. Enter custom name or press Enter to keep default:")
    custom_name = input().strip()
    if custom_name == "":
        name = default_name
    else:
        name = custom_name

    entry = create_entry(exe, name)

    vdf_path = get_shortcuts_vdf_path(steam_id)
    if not vdf_path:
        print("Could not find Steam shortcuts.vdf.")
        input("Press Enter to exit...")
        return

    backup_path = vdf_path + ".bak"
    if not os.path.exists(backup_path):
        with open(vdf_path, "rb") as original, open(backup_path, "wb") as backup:
            backup.write(original.read())

    try:
        with open(vdf_path, "rb") as f:
            data = vdf.binary_load(f)
    except Exception as e:
        print(f"Error reading shortcuts.vdf: {e}")
        data = {}

    shortcuts = data.get("shortcuts", {})
    new_index = str(len(shortcuts))
    shortcuts[new_index] = entry
    data["shortcuts"] = shortcuts

    with open(vdf_path, "wb") as f:
        vdf.binary_dump(data, f)

    print(f"Added '{name}' to Steam non-Steam games.")

    restart_steam()

    input("Done. Press Enter to exit...")
