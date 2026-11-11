'use client';
import {useState} from 'react';
const API=process.env.NEXT_PUBLIC_API_URL||'http://localhost:8000';
type Report=Record<string,unknown>;
export default function ProvenanceV4({momentId,videoId}:{momentId:string;videoId:string}){
 const [akaze,setAkaze]=useState<Report|null>(null);
 const [watermark,setWatermark]=useState<Report|null>(null);
 const [graph,setGraph]=useState<Report|null>(null);
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState('');
 async function submit(type:'verify-akaze'|'verify-watermark',file:File){
  setBusy(true);setError('');
  try{
   const body=new FormData();body.append('file',file);
   const response=await fetch(`${API}/api/moments/${momentId}/${type}`,{method:'POST',body});
   const data=await response.json();
   if(!response.ok)throw Error(JSON.stringify(data));
   if(type==='verify-akaze')setAkaze(data);else setWatermark(data);
  }catch(e){setError(String(e));}finally{setBusy(false)}
 }
 async function fetchGraph(){setBusy(true);setError('');try{
  const r=await fetch(`${API}/api/videos/${videoId}/narrative-graph`);
  const d=await r.json();if(!r.ok)throw Error(JSON.stringify(d));setGraph(d);
 }catch(e){setError(String(e));}finally{setBusy(false)}}
 function download(){window.open(`${API}/api/moments/${momentId}/marked-frame`,'_blank','noopener,noreferrer')}
 return <div style={{borderTop:'1px solid #314562',paddingTop:14,marginTop:14}}>
  <h4 style={{margin:'0 0 8px'}}>Phase 4 · Provenance lab</h4>
  <p className="small">AKAZE compares visual keypoints; keyed DCT watermark is embedded in a separate downloadable <b>still frame</b>, not the original MP4.</p>
  <label className="field">AKAZE: compare cropped/resized source frame<input disabled={busy} type="file" accept="image/*" onChange={e=>{const f=e.target.files?.[0];if(f)void submit('verify-akaze',f)}}/></label>
  {akaze&&<p role="status" className="small">AKAZE: {akaze.candidate_visual_match?'Geometric candidate match':'Insufficient match'} · {String(akaze.inliers)} RANSAC inliers / {String(akaze.ratio_matches)} candidate matches · {String(akaze.inlier_ratio)} inlier ratio.</p>}
  <button className="secondary" type="button" disabled={busy} onClick={download} style={{width:'100%',margin:'6px 0'}}>Download keyed watermarked PNG</button>
  <label className="field">Verify watermark: upload marked PNG (or JPEG copy)<input disabled={busy} type="file" accept="image/*" onChange={e=>{const f=e.target.files?.[0];if(f)void submit('verify-watermark',f)}}/></label>
  {watermark&&<p role="status" className="small">Watermark: {watermark.watermark_detected?'DETECTED':'NOT DETECTED'} · {String(watermark.tag_bits_matched)}/32 bits · agreement {String(watermark.vote_agreement)}.</p>}
  <button type="button" className="secondary" disabled={busy} style={{width:'100%',marginTop:6}} onClick={()=>void fetchGraph()}>Show narrative relationships</button>
  {graph&&<div className="small" role="status" style={{overflowWrap:'anywhere'}}>Graph source: {String(graph.source)} · {Array.isArray(graph.nodes)?graph.nodes.length:0} nodes · {Array.isArray(graph.edges)?graph.edges.length:0} edges.</div>}
  {error&&<p role="alert" style={{color:'#ffb7b7',overflowWrap:'anywhere'}}>{error}</p>}
 </div>
}
