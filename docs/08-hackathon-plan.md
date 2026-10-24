# Demo runbook

Reviewed **24 October 2026**. This replaces the original build schedule with a walkthrough of what exists now.

**Open [Civic](https://mubit-hunters.onrender.com/).** Allow for a cold start if the hosting plan sleeps. The sample ticket needs no account; real driver accounts use Neon email codes.

## Three-minute walkthrough

1. **Introduce the problem:** a driver has a parking notice and needs to understand the facts, evidence and next step. Point to the homepage's sourced industry context, not invented customer successes.
2. **Open Demo ticket:** show the fictional notice. Run live Mubit extraction, inspect the extracted fields and confirm them. Explain that a real driver can correct facts or enter them manually.
3. **Assess:** show the sample payment receipt and ask for guidance. Highlight grounds, evidence gaps, risks and linked sources. When available, show the returned model/request ID as evidence of a live call. The fictional sample requests full recording; show its requested mode, then inspect Mubit’s task count separately before claiming it became a training example.
4. **Review the draft:** edit, approve and download the watermarked example. Explain that the user submits through the issuer; Civic has not sent an appeal or cancelled a charge.
5. **Show the map:** search a London destination, select a location and inspect recorded restrictions/directions. No live vacancy claim.
6. **Finish with the real account flow:** sign up, keep private cases, upload evidence, prepare a pack and track the response. Do not create fake verified outcomes to fill the dashboard.

## If a service is unavailable

Choose the explicit **sample walkthrough** when Mubit fails; its answers are prewritten and labelled. Never present them as live model output. Reload or **Start again** resets the demo. Runs do not count toward customer activity. Demo quotas and state expiry are described in [capacity](CAPACITY.md).

Map failures should leave list browsing usable; geocoder failure still permits map browsing. Use the isolated local setup in [deployment](DEPLOYMENT.md#local-development) if the hosted frontend is unavailable. A local sample walkthrough does not prove live signup or inference.

## Optional council/learning segment

The separate council workspace demonstrates synthetic review, officer decisions, optional CEO photos and exchange receipts. **Admin → Learning & evaluation** shows original answers beside owner-approved targets and permits export. The after-training result remains pending: no automatic correction submission or trained-adapter activation is connected. [Feedback status](MUBIT-FEEDBACK.md).

Live consumer demo inference was verified on 24 October 2026 using `gpt-6-luna` through Mubit. Recheck a changed provider configuration before a presentation; do not manufacture calls to reach a provider training threshold. Record only non-sensitive demo data and keep credentials/approval links off screen.

Event track, judging criteria and submission deadlines must be confirmed against the organiser's current instructions; this document makes no claim of eligibility or award alignment.
