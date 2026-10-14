"use client";


import {
  useState
} from "react";


import {
  ArrowRight,
  Eye,
  EyeOff,
  LoaderCircle
} from "lucide-react";


import {
  primeVectorAudio
} from "../../components/ui/vector-sound";
import {
  primeCinematicAudio,
  playCinematicWarp
} from "../../components/ui/vector-cinematic-audio";


import { runVectorGravityTransition } from "../../components/ui/vector-gravity-transition";

export default function LoginForm({
  defaultUsername
}) {
  const [
    username,
    setUsername
  ] =
    useState(
      defaultUsername ||
      ""
    );


  const [
    password,
    setPassword
  ] =
    useState(
      ""
    );


  const [
    revealPassword,
    setRevealPassword
  ] =
    useState(
      false
    );


  const [
    error,
    setError
  ] =
    useState(
      ""
    );


  const [
    loading,
    setLoading
  ] =
    useState(
      false
    );


  async function login(
    event
  ) {
    event.preventDefault();


    void primeVectorAudio();
    void primeCinematicAudio();


    if (
      loading
    ) {
      return;
    }


    setLoading(
      true
    );

    setError(
      ""
    );


    try {
      const response =
        await fetch(
          "/api/auth/login",
          {
            method:
              "POST",

            headers: {
              "Content-Type":
                "application/json"
            },

            body:
              JSON.stringify({
                username,
                password
              })
          }
        );


      if (
        !response.ok
      ) {
        if (
          response.status ===
          429
        ) {
          const seconds =
            Number(
              response.headers.get(
                "Retry-After"
              ) ||
              0
            );


          const minutes =
            Math.max(
              1,
              Math.ceil(
                seconds /
                60
              )
            );


          setError(
            `Too many attempts. Try again in about ${minutes} minute${minutes === 1 ? "" : "s"}.`
          );

        } else {
          setError(
            "Invalid username or password."
          );
        }


        setLoading(
          false
        );

        return;
      }


      sessionStorage.setItem(
        "vector:intro:pending",
        "1"
      );

      // Start only after successful authentication.
      try {
        await runVectorGravityTransition({
          playSound: playCinematicWarp
        });
      } catch (animationError) {
        console.warn(
          "Vector transition fallback",
          animationError
        );
      }

      // Start a new document, not a soft navigation with a cached owner UI.
      window.location.replace("/");

    } catch {
      setError(
        "Vector could not be reached."
      );

      setLoading(
        false
      );
    }
  }


  return (
    <form
      className="vector-premium-login-form"
      onSubmit={login}
    >
      {
        error && (
          <div
            className="login-error vector-login-error"
            role="alert"
          >
            {error}
          </div>
        )
      }


      <div className="form-group">

        <label
          className="form-label"
          htmlFor="username"
        >
          Username
        </label>


        <input
          className="form-input"
          id="username"
          name="username"
          type="text"
          autoComplete="username"
          spellCheck="false"
          maxLength={128}
          value={username}
          onChange={
            event =>
              setUsername(
                event.target.value
              )
          }
          required
        />

      </div>


      <div className="form-group">

        <label
          className="form-label"
          htmlFor="password"
        >
          Password
        </label>


        <div className="vector-password-field">

          <input
            className="form-input"
            id="password"
            name="password"
            type={
              revealPassword
                ? "text"
                : "password"
            }
            autoComplete="current-password"
            maxLength={1024}
            value={password}
            onChange={
              event =>
                setPassword(
                  event.target.value
                )
            }
            required
          />


          <button
            className="vector-password-toggle"
            type="button"
            aria-label={
              revealPassword
                ? "Hide password"
                : "Show password"
            }
            onClick={
              () =>
                setRevealPassword(
                  current =>
                    !current
                )
            }
          >
            {
              revealPassword
                ? (
                    <EyeOff
                      aria-hidden="true"
                    />
                  )
                : (
                    <Eye
                      aria-hidden="true"
                    />
                  )
            }
          </button>

        </div>

      </div>


      <button
        className="primary-button vector-login-submit"
        type="submit"
        disabled={loading}
      >
        <span>
          {
            loading
              ? "Connecting"
              : "Enter Vector"
          }
        </span>

        <span
          className="vector-login-submit-icon"
        >
          {
            loading
              ? (
                  <LoaderCircle
                    className="vector-login-spinner"
                    aria-hidden="true"
                  />
                )
              : (
                  <ArrowRight
                    aria-hidden="true"
                  />
                )
          }
        </span>
      </button>

    </form>
  );
}
