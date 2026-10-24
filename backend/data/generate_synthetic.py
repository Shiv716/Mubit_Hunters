"""Generates synthetic demo cases and the fixed labelled evaluation dataset.

All data is synthetic: VRMs use the fake 'SYN' prefix, PCN refs the 'DM' prefix, locations are invented.
Gold labels encode how the (synthetic) demo council applies its policy, including discretionary areas where the
deterministic rules alone say 'needs_review'. Those discretionary cases are where reviewed precedents can help.

Run: python data/generate_synthetic.py   (outputs are committed; re-running with the same seed is reproducible)
"""
from __future__ import annotations

import hashlib
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parent
SEED = 20261024
DATASET_VERSION = "pcn-eval-v1"

STREETS = ["Elm Row", "Harbour Lane", "Mill Street", "Kings Parade", "Orchard Way", "Station Approach",
           "Victoria Terrace", "Bridge Road", "Quarry Hill", "Linden Close", "Abbey Walk", "Market Square"]
ZONES = ["Z1", "Z2", "Z3", "Z4"]


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


class Builder:
    def __init__(self, rng: random.Random, prefix: str):
        self.rng, self.prefix, self.n = rng, prefix, 0

    def base(self, code: str, grounds: list[str], text: str, *, late: bool = False, obs: int | None = None) -> dict:
        self.n += 1
        r = self.rng
        t = datetime(2026, r.randint(6, 9), r.randint(1, 28), r.randint(8, 18), r.choice([0, 7, 15, 22, 34, 41, 53]))
        notice = t.date() + timedelta(days=r.randint(0, 3))
        received = notice + timedelta(days=r.randint(35, 50) if late else r.randint(2, 25))
        vrm = f"SYN{r.randint(1000, 9999)}"
        street = r.choice(STREETS)
        pcn = f"DM{self.prefix}{self.n:06d}"
        return {
            "pcn_ref": pcn, "vrm": vrm, "contravention_code": code,
            "contravention_datetime": t.isoformat(), "location": f"{street}, Demo Borough", "zone": r.choice(ZONES),
            "notice_date": notice.isoformat(), "representation_received_date": received.isoformat(),
            "representation_text": text, "claimed_grounds": grounds, "observation_minutes": obs,
            "stage": "formal",
            "response_due_date": (datetime(2026, 10, 27) + timedelta(days=2 * (self.n - 1))).date().isoformat(),
            "prior_undisplayed_permit_count": 0,
            "evidence": [{"id": "E1", "type": "ceo_photo", "source": "council",
                          "description": "Civil enforcement officer photographs of vehicle and signage",
                          "filename": f"{pcn}_ceo.jpg", "sha256": _sha(pcn + "ceo"),
                          "captured_at": t.isoformat(), "vrm_seen": vrm, "location_seen": street}],
            "records": {}, "synthetic": True,
        }

    def add_ev(self, case: dict, etype: str, desc: str, **kw) -> None:
        eid = f"E{len(case['evidence']) + 1}"
        case["evidence"].append({"id": eid, "type": etype, "source": "motorist", "description": desc,
                                 "filename": f"{case['pcn_ref']}_{eid}.pdf",
                                 "sha256": _sha(case["pcn_ref"] + eid), **kw})


def _t(case: dict) -> datetime:
    return datetime.fromisoformat(case["contravention_datetime"])


def _pay(case: dict, start_off: int, end_off: int, same_zone: bool = True) -> dict:
    t = _t(case)
    zone = case["zone"] if same_zone else ("Z9")
    return {"reference": f"PAY-{case['pcn_ref'][-5:]}", "vrm": case["vrm"], "zone": zone,
            "start": (t + timedelta(minutes=start_off)).isoformat(), "end": (t + timedelta(minutes=end_off)).isoformat()}


def _permit(case: dict, valid: bool, displayed: bool | None) -> dict:
    t = _t(case)
    frm, to = (t - timedelta(days=100), t + timedelta(days=200)) if valid else (t - timedelta(days=400), t - timedelta(days=30))
    return {"permit_id": f"PRM-{case['pcn_ref'][-5:]}", "vrm": case["vrm"], "zone": case["zone"],
            "valid_from": frm.isoformat(), "valid_to": to.isoformat(), "displayed": displayed}


def _badge(case: dict, valid: bool, displayed: bool | None) -> dict:
    d = _t(case).date()
    frm, to = (d - timedelta(days=300), d + timedelta(days=400)) if valid else (d - timedelta(days=1200), d - timedelta(days=20))
    return {"badge_id": f"BB-{case['pcn_ref'][-5:]}", "valid_from": frm.isoformat(), "valid_to": to.isoformat(),
            "displayed": displayed}


# Each scenario: (name, gold_label, officer_reason, texts, build(builder, text) -> case)
def scenarios():
    def paid_covered(b, text):
        c = b.base("11", ["paid"], text)
        b.add_ev(c, "payment_receipt", "Screenshot of app payment confirmation")
        c["records"]["payments"] = [_pay(c, -30, 60)]
        return c

    def paid_not_found(b, text):
        c = b.base("11", ["paid"], text)
        c["records"]["payments"] = [_pay(c, -240, -120)]
        return c

    def paid_wrong_zone(b, text):
        c = b.base("11", ["paid"], text)
        b.add_ev(c, "payment_receipt", "Receipt from pay-and-display machine")
        c["records"]["payments"] = [_pay(c, -20, 90, same_zone=False)]
        return c

    def grace(b, text):
        c = b.base("05", ["paid"], text)
        c["records"]["payments"] = [_pay(c, -120, -b.rng.randint(3, 8))]
        return c

    def permit_valid(b, text):
        c = b.base("12", ["permit"], text)
        c["records"]["permits"] = [_permit(c, True, True)]
        return c

    def permit_undisplayed_first(b, text):
        c = b.base("12", ["permit"], text)
        c["records"]["permits"] = [_permit(c, True, False)]
        return c

    def permit_expired(b, text):
        c = b.base("12", ["permit"], text)
        c["records"]["permits"] = [_permit(c, False, True)]
        return c

    def badge_expired(b, text):
        c = b.base("40", ["blue_badge"], text)
        c["records"]["badges"] = [_badge(c, False, True)]
        return c

    def badge_valid_undisplayed(b, text):
        c = b.base("40", ["blue_badge"], text)
        c["records"]["badges"] = [_badge(c, True, False)]
        return c

    def short_observation(b, text):
        return b.base("01", ["loading"], text, obs=b.rng.randint(1, 3))

    def loading_with_note(b, text):
        c = b.base("01", ["loading"], text, obs=b.rng.randint(6, 12))
        b.add_ev(c, "delivery_note", "Signed delivery note with timestamp")
        return c

    def loading_no_note(b, text):
        return b.base("01", ["loading"], text, obs=b.rng.randint(8, 20))

    def medical_with_letter(b, text):
        c = b.base("01", ["medical_emergency"], text, obs=b.rng.randint(6, 15))
        b.add_ev(c, "medical_letter", "Letter from hospital confirming attendance")
        return c

    def medical_no_letter(b, text):
        return b.base("01", ["medical_emergency"], text, obs=b.rng.randint(6, 15))

    def signage_photo(b, text):
        c = b.base("01", ["signage"], text, obs=b.rng.randint(6, 15))
        b.add_ev(c, "signage_photo", "Photo of sign partially covered by foliage")
        return c

    def vrm_mismatch(b, text):
        c = b.base("11", ["paid"], text)
        c["evidence"][0]["vrm_seen"] = "SYN0000"
        c["records"]["payments"] = [_pay(c, -30, 60)]
        return c

    def late_but_paid(b, text):
        c = b.base("11", ["paid"], text, late=True)
        c["records"]["payments"] = [_pay(c, -15, 45)]
        return c

    return [
        ("paid_covered", "accept", "Verified payment covers the time and zone.", [
            "I paid using the parking app before I left the car. The session was still running when the ticket was issued.",
            "I had paid for two hours by phone. Please check your records, my payment was valid.",
            "The machine took my card payment and I have the confirmation. I was within my paid time.",
            "Paid on the app at the start of my stay, the receipt is attached.",
            "My partner paid for the parking on her phone for my car; it should show on your system.",
        ], paid_covered),
        ("paid_not_found", "reject", "No payment covers the contravention time; earlier session had ended.", [
            "I always pay for parking here, I must have paid.",
            "I paid earlier that day so I should not have been ticketed.",
            "I thought my morning payment would cover the afternoon.",
            "I am sure I paid, I just don't have the receipt any more.",
            "I paid at lunchtime, the ticket must be wrong.",
        ], paid_not_found),
        ("paid_wrong_zone", "reject", "Payment was made for a different zone.", [
            "I paid at the machine on the corner, here is the receipt.",
            "My receipt shows I paid. The zone signs are confusing but I did pay.",
            "I paid for parking on the next street, I did not realise it was a different zone.",
            "Attached is my receipt, I paid for 90 minutes.",
            "I bought a ticket from the machine nearest my car.",
        ], paid_wrong_zone),
        ("grace", "accept", "Notice issued inside the grace period after paid time.", [
            "My time had only just run out when the warden issued the ticket. I was walking back to the car.",
            "I was a few minutes late back to the car, surely there is some leeway.",
            "The ticket was issued just after my paid time ended, I was literally on my way.",
            "I overran by a couple of minutes only.",
            "I returned moments after the expiry, the officer was already writing the ticket.",
        ], grace),
        ("permit_valid", "accept", "Valid permit for vehicle and zone on council records.", [
            "I have a resident's permit for this zone and it was on the dashboard.",
            "I live on this street and hold a valid permit.",
            "My resident permit covers this bay. I don't understand why I was ticketed.",
            "Permit was displayed, please check your system.",
            "I am a permit holder for this zone.",
        ], permit_valid),
        ("permit_undisplayed_first", "accept",
         "Council practice: first occurrence of a valid but undisplayed permit is accepted.", [
            "My permit had fallen off the windscreen onto the floor. It is valid, please check.",
            "I forgot to put the permit back after cleaning the car. It is valid for this zone.",
            "The permit slipped down behind the dashboard. I have held a permit for years.",
            "I had moved the permit to my other car by mistake, but this car is registered on it.",
            "The permit was in the glovebox, it is valid and in my name.",
        ], permit_undisplayed_first),
        ("permit_expired", "reject", "Permit had expired before the contravention.", [
            "I have a resident's permit, I have always had one.",
            "I thought my permit was still valid, I renewed it I think.",
            "I live here and should be allowed to park.",
            "My permit covers this street.",
            "I have been parking here for years with a permit.",
        ], permit_expired),
        ("badge_expired", "reject", "Blue badge expired before the contravention date.", [
            "I am a blue badge holder and the badge was displayed.",
            "My badge was on the dashboard, I am disabled.",
            "I have a blue badge, the ticket is unfair.",
            "I hold a disabled badge and was entitled to park there.",
            "I displayed my badge as usual.",
        ], badge_expired),
        ("badge_valid_undisplayed", "accept",
         "Council practice: valid badge not displayed is accepted on first occurrence.", [
            "My blue badge fell off the dashboard when I closed the door. It is valid.",
            "I forgot to display my badge that day but it is valid, copy attached.",
            "The badge was face down by mistake. It is a valid badge.",
            "My carer drove and forgot to put the badge out. The badge is valid.",
            "The badge was in my bag; I am entitled to use the bay.",
        ], badge_valid_undisplayed),
        ("short_observation", "accept", "Observation period below the policy minimum.", [
            "I was unloading shopping for my elderly mother and was only there a moment.",
            "I stopped to unload heavy boxes, the ticket was issued almost immediately.",
            "I was loading my van, I was there for a very short time.",
            "Unloading a parcel, the warden did not wait at all.",
            "I was dropping off goods at the shop, it took two minutes.",
        ], short_observation),
        ("loading_with_note", "accept", "Loading supported by a delivery note.", [
            "I was making a delivery to the shop, the delivery note is attached.",
            "Delivering furniture to a customer; signed delivery note attached.",
            "I was unloading stock for the cafe; here is the delivery paperwork.",
            "Courier delivery in progress, signed proof of delivery attached.",
            "Loading equipment into the venue, see the delivery note.",
        ], loading_with_note),
        ("loading_no_note", "reject", "Loading claimed without documentary evidence.", [
            "I was just loading the car.",
            "I was unloading for a few minutes only.",
            "Dropping things off, it was quick.",
            "I was loading, I did nothing wrong.",
            "I had to unload, there was nowhere else to stop.",
        ], loading_no_note),
        ("medical_with_letter", "accept",
         "Council practice: documented medical emergency is accepted.", [
            "My son had an asthma attack and I rushed him into the clinic. The hospital letter is attached.",
            "I had to take my father to A&E urgently; letter from the hospital attached.",
            "Medical emergency, I was taken ill in the car. Letter from my GP attached.",
            "My wife went into labour, hospital confirmation attached.",
            "I attended the urgent care centre, see the attached letter.",
        ], medical_with_letter),
        ("medical_no_letter", "reject", "Unsupported mitigation.", [
            "I felt unwell so I stopped.",
            "It was an emergency.",
            "I had a family emergency and had to stop.",
            "I was ill that day.",
            "Medical reasons, I had to stop.",
        ], medical_no_letter),
        ("signage_photo", "needs_review", "Credible signage claim requires a site check.", [
            "The sign was covered by a tree, see my photo.",
            "There was no visible sign, the post was bent away from the road. Photo attached.",
            "The yellow lines are worn away and the sign is hidden. Photos attached.",
            "The restriction sign was obscured by scaffolding, photo attached.",
            "I could not see any sign, photo attached showing it covered.",
        ], signage_photo),
        ("vrm_mismatch", "needs_review", "Evidence VRM does not match the case; refer for investigation.", [
            "I paid by app, my session was running.",
            "The ticket is for my car but I had paid.",
            "I paid, check your records.",
            "I had a valid parking session on the app.",
            "Paid by phone before leaving the car.",
        ], vrm_mismatch),
        ("late_but_paid", "accept",
         "Council practice: late representation accepted where payment is verified.", [
            "Sorry this is late, I was abroad. I had paid by app at the time.",
            "I only just found the notice. I had paid for parking that day.",
            "Apologies for the delay. My app payment was active.",
            "I was in hospital and couldn't respond in time. I paid for parking.",
            "Late reply, sorry. I had a valid payment.",
        ], late_but_paid),
    ]


def build_sets():
    rng = random.Random(SEED)
    pool_b, hold_b, demo_b = Builder(rng, "P"), Builder(rng, "H"), Builder(rng, "D")
    pool, holdout, demo = [], [], []
    for name, label, reason, texts, fn in scenarios():
        # texts[0:2] -> precedent pool, texts[2:5] -> holdout; demo uses texts[0]. No text shared across splits.
        for t in texts[:2]:
            pool.append({"scenario": name, "gold_label": label, "officer_reason": reason, "case": fn(pool_b, t)})
        for t in texts[2:5]:
            holdout.append({"scenario": name, "gold_label": label, "case": fn(hold_b, t)})
        demo.append(fn(demo_b, texts[0]))
    return pool, holdout, demo


def main():
    pool, holdout, demo = build_sets()
    dataset = {
        "dataset_version": DATASET_VERSION, "seed": SEED, "synthetic": True,
        "notice": "Synthetic data. Gold labels reflect the synthetic demo council's practice, not any real council.",
        "pool": pool, "holdout": holdout,
    }
    (OUT / "eval_dataset.json").write_text(json.dumps(dataset, indent=1), encoding="utf-8")
    (OUT / "demo_cases.json").write_text(json.dumps(demo, indent=1), encoding="utf-8")
    print(f"pool={len(pool)} holdout={len(holdout)} demo={len(demo)}")


if __name__ == "__main__":
    main()
