import os
import sys
import time
import shutil
import urllib.request
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:8000"
RECORD_DIR = Path("scratch/videos/raw")
RECORD_DIR.mkdir(parents=True, exist_ok=True)
FINAL_MP4 = Path("whatif_demo_chirag_prometheus.mp4").resolve()
ARTIFACT_DIR = Path(r"C:\Users\chira\.gemini\antigravity\brain\d331b004-98b2-4088-9254-9eb04681510d")


def ensure_server():
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=2) as resp:
            if resp.status == 200:
                print("Backend server is already running and healthy.")
                return None
    except Exception:
        pass

    print("Backend server not responding. Starting uvicorn on port 8000...")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "apps.api.main:app", "--port", "8000"],
        env=dict(os.environ, PYTHONPATH="."),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    for i in range(25):
        time.sleep(1)
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=2) as resp:
                if resp.status == 200:
                    print(f"Server ready after {i+1}s!")
                    return proc
        except Exception:
            pass
    print("Warning: server healthcheck timed out, proceeding anyway.")
    return proc


def set_caption(page, text: str, subtext: str = ""):
    page.evaluate(
        """([text, subtext]) => {
        let el = document.getElementById("demo-caption-overlay");
        if (!el) {
            el = document.createElement("div");
            el.id = "demo-caption-overlay";
            el.style = `
                position: fixed;
                bottom: 24px;
                left: 50%;
                transform: translateX(-50%);
                background: rgba(18, 30, 24, 0.94);
                backdrop-filter: blur(12px);
                color: #eef5f0;
                padding: 14px 28px;
                border-radius: 12px;
                font-family: 'DM Sans', -apple-system, sans-serif;
                border: 1px solid rgba(188, 227, 201, 0.35);
                box-shadow: 0 12px 40px rgba(0, 0, 0, 0.55);
                z-index: 9999999;
                max-width: 900px;
                width: 85%;
                text-align: center;
                pointer-events: none;
                transition: opacity 0.3s ease, transform 0.3s ease;
            `;
            document.body.appendChild(el);
        }
        el.innerHTML = `
            <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px; color: #8fa899; margin-bottom: 4px; font-weight: 600;">
                Chirag · Team PROMETHEUS | WHATIF Demo
            </div>
            <div style="font-size: 16px; font-weight: 600; color: #eef5f0; line-height: 1.4;">
                ${text}
            </div>
            ${subtext ? `<div style="font-size: 13px; color: #bce3c9; margin-top: 4px; font-weight: 400;">${subtext}</div>` : ''}
        `;
    }""",
        [text, subtext],
    )


def record():
    srv = ensure_server()
    print("Starting Playwright browser recording...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="msedge", headless=True)
            context = browser.new_context(
                viewport={"width": 1600, "height": 900},
                record_video_dir=str(RECORD_DIR),
                record_video_size={"width": 1600, "height": 900},
            )
            page = context.new_page()

            # ==========================================
            # PART 1: INTRO (0:00 - 0:25)
            # ==========================================
            print("[1/6] Loading Home Overview...")
            page.goto(BASE_URL, wait_until="domcontentloaded")
            time.sleep(2)

            set_caption(
                page,
                "WHATIF: Business Decision Simulator with Verifiable Memory",
                "Separating Math from Memory: 5,000-run NumPy Vector Twin + Hindsight Cloud Episodic Memory",
            )
            time.sleep(5)

            set_caption(
                page,
                "13-Week Cash Outlook: The Monte Carlo Uncertainty Fan",
                "Green line = median cash path (p50); shaded corridor = 80% credible range under real operational variance.",
            )
            try:
                page.hover(".fan")
            except Exception:
                pass
            time.sleep(6)

            set_caption(
                page,
                "Operational Needs Feed: Every Forecast Gets a Receipt",
                "Tracks unreviewed decisions, logs raw partner quotes, and monitors forecast calibration reliability.",
            )
            page.evaluate("window.scrollBy({top: 300, behavior: 'smooth'})")
            time.sleep(5)
            page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
            time.sleep(2)

            # ==========================================
            # PART 2: THE PROBLEM (MEMORY OFF) (0:25 - 0:55)
            # ==========================================
            print("[2/6] Demonstrating The Problem: Memory OFF...")
            set_caption(
                page,
                "The Problem: The Amnesiac Agent",
                "Testing a high-stakes Diwali campaign without historical memory.",
            )
            time.sleep(3)

            # Click Ask what if
            page.click("#askFab")
            time.sleep(2)

            # Type the compound Diwali question with realistic pacing
            question_text = "Diwali Campaign: Core price +8%, Ads +2L, restock 4,000 jars from Rajan Jars"
            set_caption(
                page,
                "Formulating Compound Decision in Natural Language",
                "Combining price hike (+8%), ad budget scaling (+₹2L), and 4,000 inventory restock.",
            )
            q_box = page.locator("#question")
            q_box.fill("")
            for ch in question_text:
                q_box.type(ch, delay=35)
            time.sleep(2)

            # Toggle Memory OFF
            set_caption(
                page,
                "Step 1: Running with Memory OFF (Generic Priors)",
                "The simulator uses generic starting assumptions without past partner delays or ad saturation.",
            )
            page.click("#memoryNo")
            time.sleep(2)

            # Parse question to decision card
            page.click("#parseQuestion")
            time.sleep(2)

            # Run 5,000 simulations
            set_caption(
                page,
                "Running 5,000 Common-Random Monte Carlo Paths...",
                "Vectorized NumPy engine simulates 13 weeks of demand, inventory arrivals, and cash flows in <15ms.",
            )
            page.click("#runSimulation")
            page.wait_for_selector(".result-hero", state="visible", timeout=30000)
            time.sleep(2)

            set_caption(
                page,
                "False Sense of Security: +₹35,000 Profit & 12% Loss Risk",
                "With Memory OFF, the system falsely recommends the plan, completely blind to real supplier lags.",
            )
            try:
                page.hover(".scenario.recommended")
            except Exception:
                pass
            time.sleep(6)

            # ==========================================
            # PART 3: THE BEFORE/AFTER MOMENT (MEMORY ON) (0:55 - 1:40)
            # ==========================================
            print("[3/6] Flipping Memory ON (Hindsight Cloud)...")
            set_caption(
                page,
                "Flipping Memory ON: arecall() Queries Hindsight Cloud Bank",
                "Retrieving past supplier delivery track records, seasonal confounders, and ad saturation limits.",
            )
            time.sleep(2)

            page.click("#resultMemoryOn")
            page.wait_for_selector(".result-hero", state="visible", timeout=30000)
            time.sleep(2)

            set_caption(
                page,
                "The Story Flips: Cash Cliff & 42% Chance Worse Off!",
                "Central profit drops and lowest cash craters to ₹22,000 in Week 4 due to Rajan Jars delay.",
            )
            try:
                page.hover(".result-hero")
            except Exception:
                pass
            time.sleep(6)

            # Scroll down to Why we think this
            set_caption(
                page,
                "Why We Think This: Citing Real Business Receipts",
                "Hindsight Cloud recalls: Rajan Jars median delay is 16 days (+3 for hedges), and Instagram ads saturate at ₹4L.",
            )
            page.evaluate("window.scrollBy({top: 400, behavior: 'smooth'})")
            time.sleep(1)

            # Ensure details is open
            page.evaluate("document.querySelector('details.evidence').open = true")
            time.sleep(6)

            # ==========================================
            # PART 4: LOCK PREDICTION RECEIPT (1:40 - 2:10)
            # ==========================================
            print("[4/6] Committing Staged Test...")
            set_caption(
                page,
                "Staging the Move: Committing the Smaller Test",
                "Instead of the risky full plan, WHATIF recommends splitting the restock and capping ads.",
            )
            page.evaluate("window.scrollTo({top: 600, behavior: 'smooth'})")
            time.sleep(2)

            page.click("#commitTest")
            time.sleep(2)

            set_caption(
                page,
                "Locking Immutable Prediction Receipt (/api/decisions/commit)",
                "Prediction range is locked in SQLite and retained in Hindsight via client.aretain(). No retrofitting.",
            )
            time.sleep(4)
            page.click("#commitForm button.primary")
            time.sleep(3)

            # Decisions Ledger
            set_caption(
                page,
                "Decisions Ledger: Every Forecast Gets a Receipt",
                "Immutable audit trail comparing predicted ranges against future actuals on review date.",
            )
            time.sleep(5)

            # ==========================================
            # PART 5: REVIEW & ATTRIBUTION GATING (2:10 - 2:35)
            # ==========================================
            print("[5/6] Reviewing with Confounders & Gating...")
            set_caption(
                page,
                "Reviewing with Confounders: The Attribution Gating Invariant",
                "Grading the forecast while tagging external noise (festival rush, logistics strike).",
            )
            page.locator("button[data-review]").first.click()
            time.sleep(2)

            page.fill("input[name='effect']", "18000")
            time.sleep(1)
            page.fill("input[name='units']", "-4.0")
            time.sleep(1)
            page.fill("input[name='tags']", "festival rush, logistics strike")
            time.sleep(1)
            page.fill(
                "textarea[name='note']",
                "Diwali festival rush and courier strike distorted baseline sales.",
            )
            time.sleep(2)

            # Grade forecast
            page.click("#reviewForm button.primary")
            time.sleep(2)

            set_caption(
                page,
                "Attribution Gating in Action: Refusing to Learn from Noise!",
                "Effective uncertainty (0.28 > 0.20) gates out noise: receipt is recorded, but numeric beliefs are NOT corrupted.",
            )
            time.sleep(6)
            try:
                page.click("#closeReviewed", timeout=2000)
            except Exception:
                page.evaluate("document.getElementById('modal')?.close()")
            time.sleep(2)

            # ==========================================
            # PART 6: REALITY LAYER & LEARN (2:35 - 3:00)
            # ==========================================
            print("[6/6] Reality Layer & Learning Scorecard...")
            page.locator(".rail button[data-page='partners']").click()
            time.sleep(1)
            set_caption(
                page,
                "The Reality Layer: Natural Language Quote Capture",
                "Pasting supplier WhatsApp messages: WHATIF extracts hedge words ('should be') and tracks delivery drift.",
            )
            time.sleep(5)

            # Learn page
            page.locator(".rail button[data-page='learn']").click()
            time.sleep(1)
            set_caption(
                page,
                "Learn: Forecast Calibration Scorecard & Reflection",
                "Tracking empirical 80% range coverage and synthesizing multi-decision insights via client.areflect().",
            )
            time.sleep(3)

            page.click("#askWhy")
            time.sleep(1)
            set_caption(
                page,
                "Hindsight Reflection: 'Why Were We Off?'",
                "Synthesizing cross-decision lessons without hallucinating numbers. Cites recorded receipts.",
            )
            time.sleep(6)
            try:
                page.click("#closeReflection", timeout=2000)
            except Exception:
                page.evaluate("document.getElementById('modal')?.close()")
            time.sleep(2)

            # Final take
            set_caption(
                page,
                "Team PROMETHEUS | WHATIF",
                "Vectorized NumPy Twin · Hindsight Cloud Memory · Groq Regex Guardrails · Band.ai Agents",
            )
            time.sleep(4)

            # Close page & context to finalize video
            page.close()
            context.close()
            browser.close()

        print("Browser session closed. Finding recorded video file...")
        recorded_files = list(RECORD_DIR.glob("*.webm"))
        if not recorded_files:
            raise RuntimeError("No recorded video found in " + str(RECORD_DIR))

        raw_video = max(recorded_files, key=lambda f: f.stat().st_mtime)
        print(f"Raw video captured: {raw_video} ({raw_video.stat().st_size} bytes)")

        print(f"Transcoding {raw_video} to high-definition MP4 via ffmpeg...")
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(raw_video),
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-r",
            "30",
            str(FINAL_MP4),
        ]
        subprocess.run(cmd, check=True)

        if ARTIFACT_DIR.exists():
            dest = ARTIFACT_DIR / "whatif_demo_chirag_prometheus.mp4"
            shutil.copy2(str(FINAL_MP4), str(dest))
            print(f"Copied MP4 to artifact directory: {dest}")

        print(f"SUCCESS! Final MP4 video created: {FINAL_MP4}")
        print(f"File size: {FINAL_MP4.stat().st_size / (1024 * 1024):.2f} MB")

    finally:
        if srv:
            print("Terminating spawned server process...")
            srv.terminate()


if __name__ == "__main__":
    record()
