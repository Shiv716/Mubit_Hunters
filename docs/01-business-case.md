# Business case — reviewed for trial-2

## Verdict

A focused paid pilot makes sense. A business is not yet validated. The strongest promise is reducing routine officer review time while keeping the officer responsible for the decision. Customer willingness to pay, integration effort and measured quality improvement remain unknown.

## Customer and product

- **User:** a parking representations / notice processing officer.
- **Buyer:** a council Head of Parking Services or an outsourced processing team.
- **Job:** bring supplied evidence, policy checks and an editable response into one review desk.
- **Value to test:** shorter review time, less rework and more consistent explanations.
- **Commercial starting point:** an add-on for one team's case export, not a replacement enforcement platform.

## Evidence, with limits

| Finding | What it supports | What it does not establish |
|---|---|---|
| London issued 9,462,185 PCNs in 2024–25 | Significant enforcement volume | These include parking, bus-lane and moving-traffic PCNs; this is not the parking-only market |
| 49.4% of decided parking tribunal appeals were allowed | There is value in reviewing the quality of challenged decisions | Tribunal cases are a selected subset; this is not the error rate of all council rejections |
| 6,143 of 10,496 allowed parking appeals were not contested | Some cases create work before the authority withdraws | Withdrawal alone does not prove officer error or that AI would have prevented it |
| Herefordshire reported 1,316 routine reasons among 2,047 cancellations in 2021–22 | Repeated evidence-checking patterns exist | The roughly 64% share describes cancellations, not all incoming reviews |
| Haringey reported 2,836 challenges and 12,851 PCNs in May 2021 | Review workload can be substantial | The roughly 22% ratio is an old, single-month correspondence proxy, not a matched cohort challenge rate |

Primary volume source: [London Councils 2024–25 enforcement statistics](https://www.londoncouncils.gov.uk/news-and-press-releases/2025/london-councils-enforcement-and-appeals-statistics-2024-25). Other reports are linked in [sources](10-sources.md).

## Competition

Unity5 already describes policy-based appeals assessment, evidence analysis, recommendations, draft letters, human override and policy feedback. A generic AI review screen is therefore not a sufficient differentiator. [Unity5 product description](https://unity5.com/articles/how-ai-is-helping-parking-teams-handle-appeals-and-challenges/).

The proposed differentiators are vendor-neutral integration, clear evidence references and demonstrably better handling of each team's recurring cases. These are hypotheses to prove, not established exclusivity or a moat. Council-specific examples require permission, quality control and enough volume before they become useful.

## Pricing and economics

The earlier £15k / £30k / £50k annual tiers are hypotheses for customer interviews. The cited £24,042 Chipside purchase was a **2006 one-off software purchase**, not evidence of a current annual subscription price. [Copeland decision](https://www.copeland.gov.uk/sites/default/files/attachments/CIS/pdf/230506_exe7.pdf).

Use the customer's own workload to estimate value:

`annual time value = cases per year × minutes saved per case ÷ 60 × loaded hourly staff cost`

Illustrative assumptions only: 20,000 reviews × 3 minutes saved ÷ 60 × £25/hour = £25,000 of staff time annually, before integration, quality assurance and inference costs. Time released is not necessarily a cash budget saving. On those assumptions, a £30,000 subscription would be difficult to justify on time alone.

Do not tie fees to fines upheld. Do not derive market size from total parking income or apply one council's correspondence ratio nationally. Build a bottom-up list of reachable teams and their actual review volumes instead.

## Pilot decision

1. Observe one team's workflow and baseline time per case.
2. Test a permitted, appropriately governed sample with independent quality review.
3. Compare completion time, editing effort, escalations and material errors by case type.
4. Price against measured value and actual integration/support cost.
5. Proceed only if the buyer sees enough benefit after those costs.

Mubit can support inference and, if verified with the account, task-specific model improvement. Lower model cost is a secondary benefit; it cannot substitute for a useful workflow or trustworthy decisions. The current application is a synthetic demo and makes no measured savings or model-training claims.
