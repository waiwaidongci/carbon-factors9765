import {loadAll} from '../api/business.js';
import {loadGreen} from '../api/green.js';
export const store={session:JSON.parse(localStorage.getItem('session')||'null'),data:{sources:[],periods:[],policies:[],runs:[],schedules:[],deliveries:[],audits:[],green:{certificates:[],reports:[],ledger:[],conservation:{ok:true}}},selected:null};
export async function reload(){store.data=await loadAll();try{store.data.green=await loadGreen()}catch(e){store.data.green={certificates:[],reports:[],ledger:[],conservation:{ok:false}}}
export function setSession(value){store.session=value;if(value)localStorage.setItem('session',JSON.stringify(value));else localStorage.removeItem('session')}
