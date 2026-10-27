const toggle=document.getElementById('toggle-password');
toggle.addEventListener('click',()=>{const input=document.getElementById('password'),show=input.type==='password';input.type=show?'text':'password';toggle.textContent=show?'Ẩn':'Hiện';toggle.setAttribute('aria-label',show?'Ẩn mật khẩu':'Hiện mật khẩu');});
