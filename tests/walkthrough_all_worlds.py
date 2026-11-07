"""Playwright automated walkthrough for WHATIF:
- Tests all 3 synthetic worlds (Ember & Wick, Northlight Studio, Brew Lane Café)
- Tests the compound Diwali decision live with Memory On and Memory Off
- Tests Commit, Review with Confounders, Scorecard, Beliefs, Partners, and Reflection
- Captures high-res screenshots for the demo report artifact
"""
import time
import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTPUT_DIR = Path("scratch/screenshots")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACT_IMG_DIR = Path(r"C:\Users\chira\.gemini\antigravity\brain\d331b004-98b2-4088-9254-9eb04681510d\screenshots")
ARTIFACT_IMG_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "http://127.0.0.1:8000"


def snap(page, name: str, full_page: bool = False):
    p1 = OUTPUT_DIR / f"{name}.png"
    p2 = ARTIFACT_IMG_DIR / f"{name}.png"
    page.screenshot(path=str(p1), full_page=full_page)
    shutil.copy2(str(p1), str(p2))
    print(f"Captured: {name}.png")


def run_walkthrough():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        print("[1/12] Loading Home Page (Ember & Wick)...")
        page.goto(BASE_URL, wait_until="networkidle")
        time.sleep(2)
        snap(page, "01_home_overview", full_page=True)

        print("[2/12] Testing Multi-World Switching: Northlight Studio (Agency)...")
        world_select = page.locator("#worldSelect")
        if world_select.is_visible():
            world_select.select_option("northlight-studio")
            page.wait_for_load_state("networkidle")
            time.sleep(2)
            snap(page, "02_world_agency", full_page=True)

        print("[3/12] Testing Multi-World Switching: Brew Lane Café (Café)...")
        world_select = page.locator("#worldSelect")
        if world_select.is_visible():
            world_select.select_option("brew-lane-cafe")
            page.wait_for_load_state("networkidle")
            time.sleep(2)
            snap(page, "03_world_cafe", full_page=True)

        print("[4/12] Switching back to Hero: Ember & Wick Candle Co...")
        world_select = page.locator("#worldSelect")
        if world_select.is_visible():
            world_select.select_option("ember-wick")
            page.wait_for_load_state("networkidle")
            time.sleep(2)
            snap(page, "04_world_ember_wick", full_page=True)

        print("[5/12] Running Live Compound Diwali Scenario (Memory On)...")
        hard_question = "Diwali Campaign: Core price +8%, Ads +2L, restock 4,000 jars from Rajan Jars"
        q_input = page.locator("#quickQuestion")
        if q_input.is_visible():
            q_input.fill(hard_question)
            page.keyboard.press("Enter")
            time.sleep(2)
            snap(page, "05_hard_question_composer")

        # Parse question / Make decision card
        parse_btn = page.locator("#parseQuestion")
        if parse_btn.is_visible():
            parse_btn.click()
            time.sleep(2)
            snap(page, "06_hard_decision_card")

        # Run 5,000 simulations
        run_btn = page.locator("#runSimulation")
        if run_btn.is_visible():
            run_btn.click()
            # Wait for result
            page.wait_for_selector(".result-hero", state="visible", timeout=30000)
            time.sleep(2)
            snap(page, "07_hard_simulation_memory_on", full_page=True)

        print("[6/12] Comparing with Memory Off...")
        mem_off_btn = page.locator("#resultMemoryOff")
        if mem_off_btn.is_visible():
            mem_off_btn.click()
            page.wait_for_selector(".result-hero", state="visible", timeout=30000)
            time.sleep(2)
            snap(page, "08_hard_simulation_memory_off", full_page=True)

        # Toggle back to Memory On
        mem_on_btn = page.locator("#resultMemoryOn")
        if mem_on_btn.is_visible():
            mem_on_btn.click()
            page.wait_for_selector(".result-hero", state="visible", timeout=30000)
            time.sleep(2)

        print("[7/12] Opening Commit Modal...")
        commit_plan_btn = page.locator("#commitPlan")
        if commit_plan_btn.is_visible():
            commit_plan_btn.click()
            time.sleep(1)
            snap(page, "09_hard_commit_modal")

            # Submit commit form
            submit_commit = page.locator("#commitForm button.primary")
            if submit_commit.is_visible():
                submit_commit.click()
                time.sleep(2)

        print("[8/12] Inspecting Decisions Ledger...")
        page.locator(".rail button[data-page='decisions']").click()
        time.sleep(2)
        snap(page, "10_decisions_ledger", full_page=True)

        print("[9/12] Testing Review Modal with Confounder Tagging...")
        first_review = page.locator("button[data-review]").first
        if first_review.is_visible():
            first_review.click()
            time.sleep(1)
            # If it opens review modal
            actual_input = page.locator("input[name='effect']")
            if actual_input.is_visible():
                actual_input.fill("-42000")
                units_input = page.locator("input[name='units']")
                if units_input.is_visible():
                    units_input.fill("-14.5")
                tags_input = page.locator("input[name='tags']")
                if tags_input.is_visible():
                    tags_input.fill("confounder, festival, diwali rush")
                note_input = page.locator("textarea[name='note']")
                if note_input.is_visible():
                    note_input.fill("Diwali rush confounded attribution; demand was distorted.")
                snap(page, "11_review_modal_input")

                grade_btn = page.locator("#reviewForm button.primary")
                if grade_btn.is_visible():
                    grade_btn.click()
                    time.sleep(2)
                    snap(page, "12_reviewed_result_modal")

            page.evaluate("document.getElementById('modal').close()")
            time.sleep(1)

        print("[10/12] Inspecting Scorecard & Calibration...")
        page.locator(".rail button[data-page='learn']").click()
        time.sleep(2)
        snap(page, "13_scorecard_learn", full_page=True)

        # Trigger reflection "Why were we off?"
        ask_why_btn = page.locator("#askWhy")
        if ask_why_btn.is_visible():
            ask_why_btn.click()
            time.sleep(2)
            snap(page, "14_reflection_modal")
            page.evaluate("document.getElementById('modal').close()")
            time.sleep(1)

        # Trigger synthetic truth reveal
        reveal_btn = page.locator("#revealTruth")
        if reveal_btn.is_visible():
            reveal_btn.click()
            time.sleep(1)
            snap(page, "15_ground_truth_modal")
            page.evaluate("document.getElementById('modal').close()")
            time.sleep(1)

        print("[11/12] Inspecting Beliefs & Partners...")
        belief_tab = page.locator("#beliefTab")
        if belief_tab.is_visible():
            belief_tab.click()
            time.sleep(2)
            snap(page, "16_beliefs_tab", full_page=True)

        page.locator(".rail button[data-page='partners']").click()
        time.sleep(2)
        snap(page, "17_partners_tab", full_page=True)

        # Add promise test
        promise_box = page.locator("#promiseMessage")
        if promise_box.is_visible():
            promise_box.fill("Rajan: jars should be ready in 10 days, hopefully Friday.")
            add_p_btn = page.locator("#addPromise")
            if add_p_btn.is_visible():
                add_p_btn.click()
                time.sleep(2)
                snap(page, "18_promise_added", full_page=True)

        print("Walkthrough completed successfully!")
        time.sleep(1)
        snap(page, "17_final_scorecard_learn", full_page=True)

        print("Walkthrough completed successfully!")
        browser.close()


if __name__ == "__main__":
    run_walkthrough()
