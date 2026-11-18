import React from 'react';
import {createRoot} from 'react-dom/client';
import {AuthComponent} from './components/ui/sign-up.jsx';
const target=document.getElementById('auth-root');
if(target){
  createRoot(target).render(<AuthComponent mode={target.dataset.mode==='login'?'login':'signup'} brandName="RepoLens"/>);
}
