import os
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

USER_DATA_DIR = r"C:\Users\19196\AppData\Local\Google\Chrome\User Data"
ZIP_PATH = r"C:\Users\19196\Documents\Codex\2026-09-28\aff-002-authorized-to-execute-phase\aff-integration\deploy\wordpress\budly-sales-agent.zip"
WP_ADMIN_UPLOAD_URL = "https://cccultivate.com/wp-admin/plugin-install.php?tab=upload"
WP_ADMIN_PLUGINS_URL = "https://cccultivate.com/wp-admin/plugins.php"

def run_deployment():
    print(f"Checking deployment package at: {ZIP_PATH}")
    if not Path(ZIP_PATH).exists():
        print("ERROR: Deployment package does not exist!")
        return False
    print(f"Package size: {Path(ZIP_PATH).stat().st_size} bytes")

    profiles_to_try = ["Default", "Profile 1", "Profile 4", "Profile 5"]
    
    with sync_playwright() as p:
        for profile in profiles_to_try:
            print(f"\n==========================================")
            print(f"Attempting browser launch with profile: {profile}")
            print(f"==========================================")
            
            try:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=USER_DATA_DIR,
                    channel="chrome",
                    headless=False,
                    args=[
                        f"--profile-directory={profile}",
                        "--no-first-run",
                        "--no-default-browser-check"
                    ]
                )
            except Exception as e:
                print(f"Failed to launch with profile {profile}: {e}")
                continue

            try:
                page = context.new_page()
                print(f"Navigating to {WP_ADMIN_UPLOAD_URL}...")
                page.goto(WP_ADMIN_UPLOAD_URL, timeout=30000)
                page.wait_for_load_state("networkidle")
                
                current_url = page.url
                title = page.title()
                print(f"Current URL: {current_url}")
                print(f"Page Title: {title}")
                
                if "wp-login.php" in current_url:
                    print(f"Profile {profile} is NOT logged in. Checking next profile...")
                    context.close()
                    continue
                
                if "wp-admin" in current_url:
                    print(f"SUCCESS: Authenticated session active in profile {profile}!")
                    
                    # 1. Look for file input for plugin zip
                    print("Looking for file upload input...")
                    file_input = page.locator("input[type='file'][name='pluginzip']")
                    if not file_input.is_visible():
                        # Maybe need to click 'Upload Plugin' button first if not open
                        upload_toggle = page.locator(".upload-view-toggle")
                        if upload_toggle.is_visible():
                            upload_toggle.click()
                            time.sleep(1)
                    
                    print(f"Setting file input to {ZIP_PATH}...")
                    file_input.set_input_files(ZIP_PATH)
                    time.sleep(1)
                    
                    print("Clicking 'Install Now'...")
                    install_button = page.locator("input[type='submit'][id='install-plugin-submit'], input[value='Install Now']")
                    install_button.click()
                    
                    print("Waiting for upload/install response...")
                    page.wait_for_load_state("networkidle")
                    time.sleep(3)
                    
                    print(f"Post-install URL: {page.url}")
                    print(f"Post-install Title: {page.title()}")
                    content = page.content()
                    
                    # Check if "Replace current with uploaded" button exists
                    if "Replace current with uploaded" in content or "overwrite" in content:
                        print("Found 'Replace current with uploaded' button. Clicking...")
                        replace_button = page.locator("a:has-text('Replace current with uploaded'), button:has-text('Replace current with uploaded')")
                        if replace_button.is_visible():
                            replace_button.click()
                            page.wait_for_load_state("networkidle")
                            time.sleep(3)
                            print(f"Post-replace URL: {page.url}")
                    
                    # Check for activation button if not active
                    if "Activate Plugin" in page.content():
                        print("Found 'Activate Plugin' button. Clicking...")
                        activate_button = page.locator("a:has-text('Activate Plugin')")
                        if activate_button.is_visible():
                            activate_button.click()
                            page.wait_for_load_state("networkidle")
                            time.sleep(3)
                    
                    # Verify on Plugins page
                    print("Navigating to Plugins page to verify activation...")
                    page.goto(WP_ADMIN_PLUGINS_URL, timeout=30000)
                    page.wait_for_load_state("networkidle")
                    plugins_content = page.content()
                    
                    is_active = "deactivate-budly-sales-agent" in plugins_content or ("Budly Sales Agent" in plugins_content and "Deactivate" in plugins_content)
                    print(f"Budly Sales Agent is Active: {is_active}")
                    
                    context.close()
                    return True
                
                context.close()
            except Exception as e:
                print(f"Error during deployment with profile {profile}: {e}")
                try:
                    context.close()
                except Exception:
                    pass

    print("ERROR: No authenticated WordPress Admin session found across all profiles.")
    return False

if __name__ == "__main__":
    success = run_deployment()
    print(f"DEPLOYMENT RESULT: {'SUCCESS' if success else 'FAILED'}")
    sys.exit(0 if success else 1)
