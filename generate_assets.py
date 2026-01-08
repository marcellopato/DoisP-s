from PIL import Image, ImageOps
import os

def generate_mobile_assets(source_path, bg_color="#1E1E1E"):
    if not os.path.exists(source_path):
        print(f"Error: {source_path} not found.")
        return

    original = Image.open(source_path).convert("RGBA")
    
    # --- 1. APP ICON (512x512) ---
    icon_size = (512, 512)
    icon_img = Image.new("RGBA", icon_size, bg_color)
    
    # Resize logo to fit with padding (e.g. 70% of icon size)
    target_logo_size = int(512 * 0.7)
    logo_for_icon = original.copy()
    logo_for_icon.thumbnail((target_logo_size, target_logo_size), Image.Resampling.LANCZOS)
    
    # Paste centered
    icon_w, icon_h = icon_img.size
    logo_w, logo_h = logo_for_icon.size
    offset = ((icon_w - logo_w) // 2, (icon_w - logo_h) // 2)
    
    icon_img.paste(logo_for_icon, offset, logo_for_icon)
    icon_img.save("app_icon.png")
    print("Generated app_icon.png")

    # --- 2. SPLASH SCREEN (1080x1920) ---
    splash_size = (1080, 1920)
    splash_img = Image.new("RGBA", splash_size, bg_color)
    
    # Resize logo to be 40% of width
    target_splash_width = int(1080 * 0.4)
    logo_for_splash = original.copy()
    
    # Calculate height maintaining aspect ratio
    aspect = original.height / original.width
    target_splash_height = int(target_splash_width * aspect)
    
    logo_for_splash = logo_for_splash.resize((target_splash_width, target_splash_height), Image.Resampling.LANCZOS)
    
    # Paste centered
    splash_w, splash_h = splash_img.size
    logo_sw, logo_sh = logo_for_splash.size
    offset_splash = ((splash_w - logo_sw) // 2, (splash_h - logo_sh) // 2)
    
    splash_img.paste(logo_for_splash, offset_splash, logo_for_splash)
    splash_img.save("splash_screen.png")
    print("Generated splash_screen.png")

if __name__ == "__main__":
    generate_mobile_assets("dois-pes.png")
