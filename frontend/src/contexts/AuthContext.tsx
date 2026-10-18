import { createContext,useContext,useEffect,useState,ReactNode } from 'react';
import { apiFetch } from '../services/api';
import { loginToken,setLoginToken } from '../services/session';

export interface AuthUser {id:string;username:string;role:'administrator'|'driver'|'parent';mode:'demo'|'real';expires_at:string;vehicle_ids:string[];student_ids:string[]}
const AuthContext=createContext<{user:AuthUser|null;loading:boolean;error:string;login:(username:string,password:string,mode:string)=>Promise<void>;logout:()=>Promise<void>}|null>(null);
export function AuthProvider({children}:{children:ReactNode}){
  const [user,setUser]=useState<AuthUser|null>(null),[loading,setLoading]=useState(true),[error,setError]=useState('');
  useEffect(()=>{
    let alive=true;const controller=new AbortController();
    const changed=()=>{if(!loginToken()){setUser(null);setLoading(false);}};
    window.addEventListener('saferide-session-changed',changed);
    if(loginToken())apiFetch<AuthUser>('/auth/me',controller.signal).then(u=>{if(alive){setUser(u);setError('');}})
      .catch(e=>{if(alive){setUser(null);setError(e instanceof Error?e.message:'Session check failed.');}}).finally(()=>{if(alive)setLoading(false);});
    else setLoading(false);
    return()=>{alive=false;controller.abort();window.removeEventListener('saferide-session-changed',changed);};
  },[]);
  useEffect(()=>{
    if(!user)return;
    const delay=Math.max(0,new Date(user.expires_at).getTime()-Date.now());
    const timer=setTimeout(()=>{setLoginToken(null);setUser(null);},delay);
    return()=>clearTimeout(timer);
  },[user]);
  async function login(username:string,password:string,mode:string){
    setError('');
    const value=await apiFetch<{token:string;user:AuthUser}>('/auth/login',undefined,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username,password,mode})});
    setLoginToken(value.token);setUser(value.user);
  }
  async function logout(){
    // Failed revocation is visible; don't falsely report a successful logout.
    await apiFetch('/auth/logout',undefined,{method:'POST'});
    setLoginToken(null);setUser(null);
  }
  return <AuthContext.Provider value={{user,loading,error,login,logout}}>{children}</AuthContext.Provider>;
}
export function useAuth(){const value=useContext(AuthContext);if(!value)throw new Error('AuthProvider required');return value;}
