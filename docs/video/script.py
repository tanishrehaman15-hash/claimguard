"""Narration for the ClaimGuard demo video. `say` text is spelled for the TTS voice."""

URL = "https://change-illustrations-tooth-complete.trycloudflare.com"
VOICE = "Rishi"
RATE = 168  # words per minute

# (scene id, visual, narration)
#   visual = ("slide", page_index) or ("demo", tab_name)
SCENES = [
    ("intro", ("slide", 0),
     "Hi! This is ClaimGuard. Real-time A I that pays honest insurance claims in hours, "
     "and stops fraudulent claims before the money leaves. And it is running live, on an I B M Linux One server."),
    ("problem", ("slide", 1),
     "Meet Priya. She had a small accident, and needs eighteen thousand rupees for repairs. "
     "Today she waits about two weeks, because the insurer checks every claim by hand. "
     "That queue exists to catch people like Rahul, who filed a two point four lakh rupee total loss claim, "
     "on a policy he bought just nine days ago. Manual checks are slow, they still miss organised fraud rings, "
     "and the losses come back to all of us as higher premiums."),
    ("solution", ("slide", 2),
     "ClaimGuard scores every claim the instant it is filed, and routes it to one of three lanes. "
     "Green: pay it straight away, with no manual work. Yellow: ask for one extra document in the app. "
     "Red: hold the payout, and send it to an investigator. No claim is ever rejected by a machine. "
     "A human always makes the final call."),
    ("architecture", ("slide", 3),
     "Here is how it works. When a claim arrives, our real-time feature store computes twenty six signals in microseconds. "
     "Is the bill far above the normal cost? Is the policy brand new? Is there a police report? "
     "It also keeps an identity graph, linking customers who share phone numbers or bank accounts. "
     "A gradient boosted model scores the claim in under a millisecond, exact shap reason codes explain every decision, "
     "and I B M Granite turns those reasons into a short note for the investigator."),
    ("live", ("demo", "live"),
     "This is the live dashboard, served from I B M Linux One. You can see the processor architecture in the sidebar: "
     "S 390 X. Claims stream in, and each one is scored in about a millisecond. "
     "Green claims are fast tracked instantly, and red ones are held, before any money is paid out."),
    ("investigate", ("demo", "investigate"),
     "Let's open a flagged claim. Every score comes with its reasons, so you can see exactly what pushed the risk up, "
     "such as a bill far above the typical cost, a very new policy, or links to other customers. "
     "With one click, the investigator gets a plain language note. The A I only explains. It never changes the decision."),
    ("file", ("demo", "file"),
     "Now let's file two claims ourselves. First, Priya's minor accident. Low risk. Fast tracked, and paid today. "
     "Now Rahul's total loss, on a nine day old policy, through a garage used by a group of linked customers. "
     "The risk score is close to one hundred. It goes straight to an investigator, "
     "and his message stays neutral and respectful."),
    ("rings", ("demo", "rings"),
     "This is something rule engines simply cannot see. Our identity graph connects customers through shared phones "
     "and bank accounts. Here, a whole cluster of linked customers is funnelling claims into the same garage."),
    ("model", ("demo", "model"),
     "We tested on the twelve thousand most recent claims, held out by time, so the model never saw the future. "
     "ClaimGuard stops ninety nine percent of fraudulent payout value, and fast tracks thirty seven percent of claims. "
     "At the same workload, it catches eighty one percent of fraud, compared with sixty two percent for traditional red flag rules."),
    ("ibmz", ("slide", 7),
     "Why I B M Z? Because large insurers already run their claims systems there. "
     "We compiled the full Python A I stack for S 390 X, and ClaimGuard is trained and served on I B M Linux One today. "
     "In production, the model is served through Machine Learning for Zee O S, on the Telum on-chip A I accelerator, "
     "inside the claims transaction. The data stays encrypted, and never leaves the platform."),
    ("responsible", ("slide", 8),
     "We designed it responsibly. Humans decide every high risk case. Every score has an exact reason. "
     "Customers never receive accusing messages, and no protected attributes are used. "
     "Our data is synthetic, built from public fraud red flags, and evaluated with a strict time based split."),
    ("close", ("slide", 9),
     "ClaimGuard. Honest claims paid in hours. Fraud stopped before payout. "
     "Real-time A I, right where the transaction happens, on I B M Z. Thank you!"),
]

# Two cuts from the same footage: the full YouTube version and a <=3:00 cut for the datathon form.
CUTS = {
    "full": {"rate": 180, "scenes": [s[0] for s in SCENES]},
    "short": {"rate": 186, "scenes": ["intro", "problem", "solution", "live", "investigate", "file", "model", "ibmz", "close"]},
}
