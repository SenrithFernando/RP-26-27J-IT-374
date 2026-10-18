// Per-tab bearer credential, never a URL/cookie/localStorage value. XSS can read
// sessionStorage: use HTTPS, trusted scripts and logout on shared devices.
const KEY='saferide.login';
export const loginToken=()=>sessionStorage.getItem(KEY);
export function setLoginToken(token:string|null){
  if(token)sessionStorage.setItem(KEY,token);else sessionStorage.removeItem(KEY);
  window.dispatchEvent(new Event('saferide-session-changed'));
}
export const authHeaders=():Record<string,string>=>{const token=loginToken();return token?{Authorization:`Bearer ${token}`}:{}};
