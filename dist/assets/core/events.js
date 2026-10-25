let refreshHandler=()=>{};
export const configureRefresh=fn=>refreshHandler=fn;
export const refresh=(route)=>refreshHandler(route);
export const navigate=route=>{location.hash=route;};
export const repaint=()=>refreshHandler(undefined,false);
