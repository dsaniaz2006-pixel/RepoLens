import {useCallback,useState} from 'react';
import {nextWorkspacePage} from '../state/workspaceNavigation.mjs';

// State remains local to the authenticated workspace, not global across tabs.
export function useWorkspaceNavigation(initial = 'Home') {
  const [page,setPage] = useState(initial);
  const navigate = useCallback((requested) => {
    setPage((current) => nextWorkspacePage(current,
      typeof requested === 'function' ? requested(current) : requested));
  },[]);
  return [page,navigate];
}
