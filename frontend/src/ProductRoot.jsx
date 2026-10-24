import {lazy, Suspense, useEffect, useState} from "react";
import ConsumerApp from "./ConsumerApp.jsx";
const CouncilApp = lazy(() => import("./App.jsx"));
export default function ProductRoot() {
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => {const changed = () => setHash(window.location.hash); window.addEventListener("hashchange", changed); return () => window.removeEventListener("hashchange", changed);}, []);
  return hash === "#workspace" || hash.startsWith("#approve=") ? <Suspense fallback={<div className="empty-state">Opening workspace…</div>}><CouncilApp/></Suspense> : <ConsumerApp/>;
}
