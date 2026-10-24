# Sources and provenance

Reviewed **24 October 2026**. Dates, geography, denominators and applicability must travel with a figure or rule. This is a source index, not a claim of complete legal research.

## Market context used on the homepage

| Evidence | Source / scope |
|---|---|
| 16.9m private-parking keeper lookups, 2025/26 | [RAC analysis](https://www.rac.co.uk/drive/news/motoring-news/record-17-million-private-parking-tickets-issued/); broader UK context, enforcement proxy, not unique people |
| 5,171,275 London parking PCNs, 2024/25 | [London Councils statistics](https://www.londoncouncils.gov.uk/services/parking-services/enforcement-and-appeals-statistics), [2024/25 workbook](https://www.londoncouncils.gov.uk/sites/default/files/2025-12/annual_penalty_charge_notice_statistics_2024-25.xls); TOTAL row, Total Parking PCNs column |
| 54,100 cancellations / 107,202 completed POPLA appeals | [POPLA 2025 report](https://tag-craft.files.svdcdn.com/production/assets/assets/POPLA/Annual-Reports/POPLA-Report-2025.pdf?dm=1777455861), page 5; selected appeals, includes uncontested cases, not refunds or Civic win rate |
| £29.791m Westminster PCN enforcement revenue, 2024/25 | [Council annual report](https://www.westminster.gov.uk/media/document/wcc-parking-annual-report-2024-25), page 23; includes traffic PCNs, revenue not profit |

[Consumer documentation](CONSUMER.md#homepage-figures) preserves exact methods, rounding and caveats. [MarketingImpact.jsx](../frontend/src/MarketingImpact.jsx) contains the displayed figures. £60 is an illustrative avoided payment, not a measured customer result. No verified count of unique people affected or nationwide private-parking revenue is asserted.

## Guidance supplied to the adviser

The canonical seven-entry, versioned library is [consumer-sources.json](../backend/data/consumer-sources.json). It includes GOV.UK challenge guidance, London Tribunals procedure, POPLA guidance, Department for Transport enforcement guidance, conditional keeper-liability legislation and dated private-code transition material. Each entry carries a source URL and applicability summary.

These are bundled summaries, not live retrieval or every council's rules. Preserve commencement/transition qualifications; publication does not establish that a rule applies to a notice. A future review date must not be claimed without rechecking the linked source. Validate changes with the consumer workflow checks and review the effect on generated advice.

## Map data

[OpenStreetMap](https://www.openstreetmap.org/copyright) supplies the derived London snapshot under [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/). It contains 4,339 locations from 24 October 2026. [Map documentation](PARKING-MAP.md) records the timestamp, coverage, exclusions and refresh process. [OpenFreeMap](https://openfreemap.org/quick_start/) provides rendering tiles/styles; [Photon](https://github.com/komoot/photon) supplies destination search.

## Technical references

- [Mubit API](https://docs.mubit.ai/reference/api) and [first-adapter guide](https://docs.mubit.ai/guides/first-adapter): provider capabilities, not proof that Civic's correction loop is connected. See [integration](04-mubit-integration.md).
- [Neon Auth](https://neon.com/docs/auth/overview), [Email OTP](https://neon.com/docs/auth/guides/plugins/email-otp) and [plans](https://neon.com/docs/introduction/plans): identity/configuration and provider allowances, not measured app capacity.
- [Render Docker](https://render.com/docs/docker), [Free limits](https://render.com/docs/free) and [scaling](https://render.com/docs/scaling): deployment constraints conditional on the actual subscribed plan.
- [Resend domains](https://resend.com/docs/dashboard/domains/introduction): owner-notification sender setup; driver codes use Neon.

Synthetic council policy files in `backend/policy` are demonstration fixtures, not legal authority. Mubit fixture evaluations and informal discovery conversations are not externally validated product-performance evidence.
