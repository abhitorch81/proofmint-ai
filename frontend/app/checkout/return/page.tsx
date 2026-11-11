'use client';
import Link from 'next/link';
import {Suspense,useEffect,useState} from 'react';
import {useSearchParams} from 'next/navigation';
const API=process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
function Result(){const params=useSearchParams();const [status,setStatus]=useState('Verifying PayPal sandbox capture…');const [receipt,setReceipt]=useState<unknown>(null);
 useEffect(()=>{const token=params.get('token');if(!token){setStatus('No PayPal order token supplied.');return}let ignore=false;(async()=>{try{const r=await fetch(`${API}/api/orders/${encodeURIComponent(token)}/capture`,{method:'POST'});const data=await r.json();if(!r.ok)throw Error(JSON.stringify(data));if(!ignore){setStatus('Payment completed; demo license issued.');setReceipt(data.receipt)}}catch(e){if(!ignore)setStatus(`Could not verify capture: ${String(e)}`)}})();return()=>{ignore=true}},[params]);return <><p>{status}</p>{receipt&&<pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere',background:'#15243d',padding:20,borderRadius:12}}>{JSON.stringify(receipt,null,2)}</pre>}</>}
export default function ReturnPage(){return <main className="wrap"><h1>PayPal checkout result</h1><Suspense fallback={<p>Loading…</p>}><Result/></Suspense><Link href="/">← Back to marketplace</Link></main>}
