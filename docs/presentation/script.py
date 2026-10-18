"""Two-presenter script for the ClaimGuard presentation video.

Each line: (speaker, spoken text for TTS, caption text). T = Tara (female), R = Rishi (male), both Indian English.
"""

TEAM = ["Eden Harish Dsouza", "Ayaan Arief Ahmed", "Abdul Hadi Moideen",
        "Adi Shareef", "Tanish Rehaman", "Naman Poojary"]
URL = "https://change-illustrations-tooth-complete.trycloudflare.com"
VOICES = {"T": "Tara", "R": "Rishi"}

SCENES = [
    ("hook", [
        ("T", "Eighteen thousand rupees. That's all Priya needed, after a small accident.",
              "₹18,000. That's all Priya needed after a small accident."),
        ("R", "And she waited... two whole weeks.", "And she waited... two whole weeks."),
        ("T", "Meanwhile, a fake claim for two point four lakh? Paid in two days.",
              "Meanwhile, a fake claim for ₹2.4 lakh? Paid in two days."),
    ]),
    ("intro", [
        ("R", "Hey everyone! We're team ClaimGuard. And today, we'll show you how we fixed that, with real-time A I on I B M Z.",
              "Hey everyone! We're Team ClaimGuard, and today we'll show you how we fixed that with real-time AI on IBM Z."),
    ]),
    ("problem", [
        ("T", "So, here's the problem. Insurers check almost every claim by hand.",
              "So, here's the problem. Insurers check almost every claim by hand."),
        ("R", "Which means honest people like Priya wait in the same queue as people like Rahul.",
              "Which means honest people like Priya wait in the same queue as people like Rahul."),
        ("T", "Rahul bought his policy nine days ago. No police report. And he's linked to seven other customers, through one phone number.",
              "Rahul bought his policy 9 days ago. No police report. And he's linked to 7 other customers through one phone number."),
        ("R", "Manual checks miss that. Rules miss that. And all of us pay for it, through higher premiums.",
              "Manual checks miss that. Rules miss that. And all of us pay for it through higher premiums."),
    ]),
    ("solution", [
        ("R", "ClaimGuard scores every claim, the moment it's filed, and sends it to one of three lanes.",
              "ClaimGuard scores every claim the moment it's filed, and sends it to one of three lanes."),
        ("T", "Green? We pay instantly. Yellow? We just ask for one more document.",
              "Green? We pay instantly. Yellow? We just ask for one more document."),
        ("R", "And red? The payout is held, and an investigator takes a look. A machine never rejects anyone.",
              "And red? The payout is held and an investigator takes a look. A machine never rejects anyone."),
    ]),
    ("how", [
        ("T", "Under the hood, we compute twenty six live signals for every claim. How big is the bill? How old is the policy? And who is this person connected to?",
              "Under the hood, we compute 26 live signals for every claim. How big is the bill? How old is the policy? Who is this person connected to?"),
        ("R", "A gradient boosted model scores it in under a millisecond, and every decision comes with exact reasons.",
              "A gradient-boosted model scores it in under a millisecond, and every decision comes with exact reasons."),
    ]),
    ("demo", [
        ("T", "Okay, enough slides. Let's see it live!", "Okay, enough slides. Let's see it live!"),
        ("R", "This dashboard is running right now, on an I B M Linux One server. See this? S 390 X. That's real I B M Z hardware.",
              "This dashboard is running right now on an IBM LinuxONE server. See this? s390x. That's real IBM Z hardware."),
        ("T", "Claims are streaming in, and each one is scored in about a millisecond.",
              "Claims are streaming in, and each one is scored in about a millisecond."),
        ("R", "Let's open a flagged one. Look, the bill is way above the typical cost, and every single reason is listed, right here.",
              "Let's open a flagged one. Look, the bill is way above the typical cost, and every single reason is listed right here."),
        ("T", "And with one click, the investigator gets a plain English note.",
              "And with one click, the investigator gets a plain-English note."),
        ("R", "Now, Priya's claim. Zero point six, out of a hundred. Approved, and paid today.",
              "Now, Priya's claim. 0.6 out of 100. Approved, and paid today."),
        ("T", "And Rahul? Ninety nine point two. Straight to an investigator. And notice, his message is still polite.",
              "And Rahul? 99.2. Straight to an investigator. And notice, his message is still polite."),
        ("R", "And this is my favourite part. A whole fraud ring, sharing phones and bank accounts, all using one garage.",
              "And this is my favourite part. A whole fraud ring, sharing phones and bank accounts, all using one garage."),
    ]),
    ("results", [
        ("T", "So, does it actually work?", "So, does it actually work?"),
        ("R", "On the twelve thousand most recent claims, we stopped ninety nine percent of fraudulent payout value.",
              "On the 12,000 most recent claims, we stopped 99% of fraudulent payout value."),
        ("T", "Thirty seven percent of claims get paid instantly. And we catch eighty one percent of fraud, versus sixty two percent with traditional rules.",
              "37% of claims get paid instantly. And we catch 81% of fraud, versus 62% with traditional rules."),
    ]),
    ("ibmz", [
        ("R", "Why I B M Z? Because that's where insurers' claim systems already live.",
              "Why IBM Z? Because that's where insurers' claim systems already live."),
        ("T", "We compiled the whole A I stack for Linux One. In production, the model runs on the Telum A I chip, inside the transaction, and the data never leaves the platform.",
              "We compiled the whole AI stack for LinuxONE. In production, the model runs on the Telum AI chip, inside the transaction, and the data never leaves the platform."),
    ]),
    ("close", [
        ("R", "ClaimGuard. Honest claims, paid in hours.", "ClaimGuard. Honest claims, paid in hours."),
        ("T", "Fraud, stopped before payout. Thank you!", "Fraud, stopped before payout. Thank you!"),
    ]),
]

# Pause after each line (s): short when the other presenter replies, longer at scene ends.
GAP_SAME, GAP_SWITCH, SCENE_TAIL = 0.28, 0.38, 0.55
TEMPO = {"T": 1.0, "R": 1.0}
