# User journeys

Reviewed **24 October 2026**. [Open Civic](https://mubit-hunters.onrender.com/).

## Driver: notice to appeal pack

**Sign up → scan or type → confirm → add evidence → assess → edit and approve → download → submit externally → track the response.**

1. The driver receives a notice through the issuer's normal process. Civic does not assume it arrived by post: the user can photograph a paper notice, use a screenshot or type the facts.
2. Sign up/sign in with a Neon email code. Driver access does not need council-owner approval.
3. Create a private case. Upload a JPEG/PNG/WebP or enter the notice manually; PDF pages currently need screenshots.
4. Consent to AI processing before scanning or assessment. Check the extracted issuer, reference, vehicle, dates, amount, stage and portal link. Correct omissions or mistakes; do not assume extraction authenticates the ticket.
5. Explain what happened and attach relevant evidence. Mubit assesses the supplied information with a dated source library, identifying potential grounds, missing evidence and risks. Weak cases can receive limited grounds; later/uncertain stages receive specialist help without an initial-challenge draft.
6. Edit the draft and explicitly approve it. Changed facts/evidence invalidate approval and require a current assessment before export.
7. Download the ZIP containing the draft, guidance/read-me and evidence images. **The driver submits it through the issuer's own website or postal route.** Civic does not submit or cancel the notice.
8. Optionally download an `.ics` reminder using a confirmed date. After submission, record the reference and later outcome/refund. These reports are not independently verified successes.

The stored lifecycle is `preparing → assessed → submitted → closed`; editing an assessed case can return it to preparation. Case versions and approval checks govern exports, not just the displayed status. Each case can be deleted by its owner; Auth accounts, backups and provider records have separate retention.

## No-account demo

Open [Demo ticket](https://mubit-hunters.onrender.com/#demo), inspect the fictional notice, run live extraction, confirm the result and request an assessment with the sample receipt. Review, edit, approve and download a watermarked example. If live AI is unavailable, explicitly choose the labelled sample walkthrough. Reload or start again to reset. Demo runs do not create customer cases or inflate metrics. [Runbook](08-hackathon-plan.md).

## Parking discovery

Open [Parking](https://mubit-hunters.onrender.com/#parking), search a London destination or request location access, inspect matching pins/list entries, filter recorded attributes and open directions. Check current signs and tariffs on arrival. Pins are mapped parking locations, not live vacancies or reservations. [Map coverage](PARKING-MAP.md).

## Council officer: separate workspace

At `/#workspace`, request membership, receive owner approval and verify a Neon email code. Open a synthetic case, examine supplied records/descriptions, request Mubit review, choose accept/reject/investigate, edit the response and save. Connected cases require a successful current Mubit review before a final decision; ordinary synthetic cases retain manual review.

An authorised connector can collect the human-approved result and acknowledge saving it in its source system. No real supplier connector is included, and Civic does not send the council's letter. CEO photos are optional unless selected council policy requires them. [Workspace](COUNCIL-WORKSPACE.md) · [Exchange](COUNCIL-INTEGRATION.md).
