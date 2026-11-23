"use client";

import { FormEvent, useState } from "react";
import { createClient } from "@/lib/supabase/client";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    setMessage("Entrando...");
    const supabase = createClient();
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) { setMessage(error.message); return; }
    window.location.href = "/";
  }

  return (
    <main className="login">
      <section className="card login-card">
        <div className="brand">JOB HUNTER</div>
        <p className="muted">Acesso privado ao radar.</p>
        <form onSubmit={submit} style={{display:"grid",gap:12}}>
          <input className="input" type="email" placeholder="E-mail" value={email} onChange={e=>setEmail(e.target.value)} required />
          <input className="input" type="password" placeholder="Senha" value={password} onChange={e=>setPassword(e.target.value)} required />
          <button className="button" type="submit">Entrar</button>
          <div className="muted">{message}</div>
        </form>
      </section>
    </main>
  );
}