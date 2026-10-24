import {Icon} from "./Icons.jsx";
import "./marketing.css";

// Published industry figures, checked 24 October 2026. These are not Civic outcomes.
const figures = [
  {value:"16.9m",label:"private parking enquiries to the DVLA",scope:"UK / DVLA data · 2025/26",detail:"About 46,300 keeper lookups a day to pursue parking charges. This counts enforcement activity, not individual drivers.",source:"RAC / DVLA analysis",url:"https://www.rac.co.uk/drive/news/motoring-news/record-17-million-private-parking-tickets-issued/"},
  {value:"5.17m",label:"parking PCNs issued in London",scope:"Boroughs + TfL · 2024/25",detail:"5,171,275 parking notices. Bus lane and moving traffic penalties are excluded.",source:"London Councils · official data",url:"https://www.londoncouncils.gov.uk/services/parking-services/enforcement-and-appeals-statistics"},
  {value:"50.5%",label:"of completed POPLA appeals led to cancellation",scope:"Private parking appeals · 2025 report",detail:"54,100 of 107,202 completed appeals, including cases the operator did not contest. This is not your chance of winning or Civic’s success rate.",source:"POPLA · annual report, p. 5",url:"https://tag-craft.files.svdcdn.com/production/assets/assets/POPLA/Annual-Reports/POPLA-Report-2025.pdf?dm=1777455861"},
  {value:"£29.8m",label:"PCN enforcement revenue in one London borough",scope:"Westminster · 2024/25",detail:"£29.791m reported revenue, including parking and traffic PCNs. Revenue is not profit; parking surpluses fund transport services.",source:"Westminster · annual report, p. 23",url:"https://www.westminster.gov.uk/media/document/wcc-parking-annual-report-2024-25"},
];

export default function MarketingImpact({info,onStart,busy}) {
  return <section className="driver-impact" aria-labelledby="impact-heading">
    <div className="impact-heading"><div><div className="eyebrow">PARKING IN NUMBERS / INDEPENDENT DATA</div><h2 id="impact-heading">You’re not the only one checking a ticket<span className="blue">.</span></h2></div><p>Millions of notices. Real money at stake.<br/>Start with the facts behind yours.</p></div>
    <div className="impact-grid">{figures.map(item=><article className="impact-card" key={item.label}><span className="impact-scope">{item.scope}</span><strong className="impact-number">{item.value}</strong><h3>{item.label}</h3><p>{item.detail}</p><a href={item.url} target="_blank" rel="noreferrer">{item.source}<Icon name="external" size={13}/></a></article>)}</div>
    <p className="impact-method">Published industry figures, not Civic customer results. Different periods and populations; don’t add them together. Notices and lookups do not tell us how many unique people were affected. Sources checked 24 October 2026.</p>
    <div className="impact-bottom"><div className="impact-saving"><div><span className="eyebrow">WHAT COULD YOU KEEP? / EXAMPLE</span><h3>One cancelled charge can matter.</h3><p>If you would otherwise pay £60 and the issuer cancels the unpaid charge in full, that’s £60 you keep.</p><small>Illustration, not a promised result or money saved by Civic. Use the amount you would actually pay, including any available discount. Challenging can put a discount at risk.</small></div><div className="impact-saving-amount"><strong>£60</strong><span>avoided payment<br/>if fully cancelled</span></div></div><div className="impact-action"><Icon name="spark" size={24}/><h3>Make your next move informed.</h3><p>Check your notice, bring the evidence and review a draft with Mubit.</p><button className="btn primary" disabled={busy} onClick={onStart}>Check my ticket<Icon name="arrow" size={16}/></button>{info&&<small>{info.parking_locations.toLocaleString("en-GB")} mapped parking locations · {info.source_count} dated guidance sources</small>}</div></div>
  </section>;
}
