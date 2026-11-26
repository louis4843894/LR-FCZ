import Image from 'next/image';
import './character-portrait.css';
export function CharacterPortrait({src,name,large=false}:{src:string|null;name:string;large?:boolean}){
 return src?<span className={`character-portrait${large?' character-portrait-large':''}`}><Image src={src} alt={name} width={large?128:72} height={large?160:88} loading={large?'eager':'lazy'} unoptimized/></span>:<span className="character-portrait character-portrait-missing" aria-label="角色圖片尚未取得">◇</span>;
}
