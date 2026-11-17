import {request} from './client.js';
export const loadGreen=async()=>Object.fromEntries(await Promise.all([
 ['certificates',request('/green/certificates')],
 ['reports',request('/green/reports')],
 ['ledger',request('/green/ledger')],
 ['conservation',request('/green/conservation')],
]));
export const saveCertificate=data=>request('/green/certificates','POST',data);
export const saveGreenReport=data=>request('/green/reports','POST',data);
export const enqueueGreen=id=>request('/green/reports/'+id+'/enqueue','POST',{});
export const cancelGreen=id=>request('/green/reports/'+id+'/cancel','POST',{});
