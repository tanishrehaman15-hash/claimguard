# 3-minute video script

Record your screen (QuickTime → File → New Screen Recording) with `./run.sh dashboard` open in the browser. Speak slowly; this runs about 2:50.

| Time | Screen | Say |
|---|---|---|
| 0:00–0:20 | Title slide (deck slide 1) | "Meet Priya. She had a small accident and needs ₹18,000 for repairs. Today she waits two weeks, because the insurer checks every claim by hand to catch people like Rahul, who filed a ₹2.4 lakh 'total loss' on a policy he bought nine days ago. We built ClaimGuard to fix both problems at once." |
| 0:20–0:45 | Deck slide 2–3 (problem, solution) | "Insurers lose huge sums to inflated bills, fake paperwork and organised rings, and honest customers pay for it in premiums and waiting time. ClaimGuard scores every claim the instant it's filed, inside the insurer's IBM Z claims system, and routes it: fast-track payout, a quick document check, or an investigator." |
| 0:45–1:15 | Dashboard → 📡 Live claims → ▶ Start feed | "Here's a live feed of claims. Each one is scored in about 0.2 milliseconds. Green claims are paid straight away. Over a third of all claims need no human work. Red ones are held before any money leaves." |
| 1:15–1:40 | 🔍 Investigate → pick a red claim → Generate note | "Every decision is explainable. These reason codes come from exact SHAP values: the bill is 3× the typical cost, the policy is days old, and the customer is linked to others through shared bank accounts. IBM Granite turns that into a note for the investigator, in English or Hindi. GenAI only explains; it never decides." |
| 1:40–2:05 | 📝 File a claim → Priya → Submit → Rahul → Submit | "Priya's claim: fast-tracked, paid today. Rahul's: risk 99, sent to an investigator. Notice his customer message is neutral. We never accuse anyone by machine; a human makes the final call." |
| 2:05–2:20 | 🕸️ Fraud rings → graph | "Rule engines can't see this. Our identity graph links customers sharing phones and bank accounts, and here's a ring funnelling claims into one garage." |
| 2:20–2:45 | 📊 Model & IBM Z | "On the most recent 12,000 claims, held out by time, we stop 99% of fraudulent payout value and catch 30% more fraud than rules at the same workload. And it's running live on IBM LinuxONE right now. In production on z/OS, the model is served by Machine Learning for z/OS on the Telum on-chip AI accelerator, inside the CICS transaction, with data encrypted and never leaving the platform." |
| 2:45–3:00 | Deck closing slide | "ClaimGuard: honest claims paid in hours, fraud stopped before payout. Real-time AI, right where the transaction happens, on IBM Z." |

**Tips:** 1080p, close other tabs, zoom the browser to 110%, and upload to YouTube as *Unlisted* (not Private) so judges can open it.
