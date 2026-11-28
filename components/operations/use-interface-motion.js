'use client';
import {useEffect,useState} from 'react';
export function useInterfaceMotion(){
 const [reduced,setReduced]=useState(false);
 useEffect(()=>{const media=matchMedia('(prefers-reduced-motion: reduce)');const update=()=>setReduced(media.matches||document.querySelector('.vector-shell')?.dataset.motion==='reduced');update();media.addEventListener('change',update);window.addEventListener('vector:interface-change',update);return()=>{media.removeEventListener('change',update);window.removeEventListener('vector:interface-change',update)}},[]);
 return reduced;
}
