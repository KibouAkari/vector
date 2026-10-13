import {
  redirect
} from "next/navigation";


import LoginForm
  from "./login-form";


import VectorCelestialField from "../../components/ui/vector-celestial-field";

import EventHorizon
  from "../../components/ui/event-horizon";


import {
  getSession
} from "../../lib/auth";


export const dynamic =
  "force-dynamic";


export default async function LoginPage() {
  const session =
    await getSession();


  if (
    session
  ) {
    redirect(
      "/"
    );
  }


  return (
    <main className="vector-login-page vector-login-premium">

      <div className="vector-login-space">
        <EventHorizon
          mode="login"
        />
      </div>

      <div className="vector-login-atmosphere" />
      <VectorCelestialField />


      <section className="vector-login vector-login-premium-panel">

        <div className="vector-logo vector-login-brand">

          <div className="vector-mark canonical-vector-mark">
            &lt;
          </div>

          <div className="vector-wordmark">
            Vector
          </div>

        </div>


        <div className="vector-login-heading">

          <h1 className="login-title">
            Welcome back.
          </h1>



        </div>


        <div className="login-card vector-login-card">

          <LoginForm
            defaultUsername={
              process.env
                .VECTOR_ADMIN_USER
            }
          />

        </div>

      </section>




    </main>
  );
}
