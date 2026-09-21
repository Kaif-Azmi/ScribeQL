import { useState } from "react";
import { Link } from "react-router-dom";
import LogoMark from "../components/LogoMark.jsx";
import SiteHeader from "../components/layout/SiteHeader.jsx";
import Footer from "../components/layout/Footer.jsx";
import styles from "./LandingPage.module.css";

const STACK = [
  { name: "PostgreSQL", logo: "https://cdn.simpleicons.org/postgresql/8BA8FF" },
  { name: "pgvector", logo: "https://cdn.simpleicons.org/postgresql/8BA8FF", badge: "vector" },
  { name: "sqlglot", logo: "https://cdn.simpleicons.org/python/8BA8FF", badge: "SQL" },
  { name: "FastAPI", logo: "https://cdn.simpleicons.org/fastapi/8BA8FF" },
  { name: "Gemini", logo: "https://cdn.simpleicons.org/googlegemini/8BA8FF" },
  { name: "Google", logo: "https://cdn.simpleicons.org/google/8BA8FF" },
];

const STEPS = [
  {
    title: "Sign in and verify",
    body: "Google or email and password. There is no anonymous studio — Try for free still creates a verified account.",
  },
  {
    title: "Pick a mode",
    body: "Demo runs live on a frozen Postgres e-commerce schema. Custom uploads DDL for Postgres or MySQL and never executes it.",
  },
  {
    title: "Ask, then get checked SQL",
    body: "RAG, generation, AST allowlist, and sqlglot all run on the server. Demo returns rows. Custom returns SQL only.",
  },
];

const FAQS = [
  {
    q: "How do I get started?",
    a: "Sign in with Google or email, verify if needed, then choose Demo or Use my schema. Sessions last 24 hours.",
  },
  {
    q: "Does custom mode run my SQL?",
    a: "Never. Uploaded schemas are parsed into a catalog. You get validated SQL and a Not executed banner.",
  },
  {
    q: "What languages can I ask in?",
    a: "English or Hinglish, up to 500 characters. Demo includes example chips; they hit the same /query endpoint.",
  },
  {
    q: "How is data handled?",
    a: "Questions, schemas, and hints go to a third-party AI provider. Account email and query logs stay until you delete the account.",
  },
  {
    q: "What are the limits?",
    a: "20 queries and 3 successful schema uploads per day, resetting at 00:00 UTC. Fully cached queries do not use the query allowance.",
  },
];

export default function LandingPage() {
  const [step, setStep] = useState(0);

  return (
    <div className={styles.page}>
      <SiteHeader />

      <section className={styles.hero}>
        <p className={styles.badge}>
          <LogoMark className={styles.badgeMark} />
          Presenting ScribeQL
        </p>
        <h1 className={styles.title}>
          Bring questions to life
          <br />
          with ScribeQL
        </h1>
        <Link className={styles.cta} to="/signin">
          Try for free
        </Link>

        <div className={styles.horizon} aria-hidden="true">
          <span className={styles.horizonLeft} />
          <span className={styles.horizonRight} />
        </div>

        <div className={styles.deviceWrap}>
          <figure className={styles.device} aria-label="Studio chat preview">
          <aside className={styles.rail}>
            <div className={styles.railBrand}>
              <LogoMark className={styles.mark} />
              ScribeQL
            </div>
            <span className={styles.railActive}>Demo</span>
            <span>Custom schema</span>
            <span>Account</span>
          </aside>
          <div className={styles.chat}>
            <div className={styles.chatHead}>
              <span className={styles.live} />
              Demo · Postgres
              <em>14 / 20 queries today</em>
            </div>
            <div className={styles.thread}>
              <div className={styles.msgUser}>
                Top 5 customers by total spend last month
              </div>
              <div className={styles.msgBot}>
                <div className={styles.botMeta}>
                  <LogoMark className={styles.botMark} />
                  <strong>ScribeQL</strong>
                  <span className={styles.okPill}>Executed · read-only</span>
                </div>
                <p>
                  Sums each customer&apos;s order totals for the previous calendar
                  month and returns the five highest.
                </p>
                <div className={styles.sqlCard}>
                  <div className={styles.sqlBar}>
                    <span>Checked SQL</span>
                    <span className={styles.copyHint}>Copy Postgres SQL</span>
                  </div>
                  <pre>
                    <code>
                      <span className={styles.kw}>SELECT</span> c.name,{" "}
                      <span className={styles.fn}>SUM</span>(o.total){" "}
                      <span className={styles.kw}>AS</span> total_spend
                      {"\n"}
                      <span className={styles.kw}>FROM</span> customers c
                      {"\n"}
                      <span className={styles.kw}>JOIN</span> orders o{" "}
                      <span className={styles.kw}>ON</span> o.customer_id = c.id
                      {"\n"}
                      <span className={styles.kw}>GROUP BY</span> c.id, c.name
                      {"\n"}
                      <span className={styles.kw}>ORDER BY</span> total_spend{" "}
                      <span className={styles.kw}>DESC</span>
                      {"\n"}
                      <span className={styles.kw}>LIMIT</span> 5
                    </code>
                  </pre>
                </div>
                <div className={styles.resultCard}>
                  <div className={styles.resultBar}>3 rows</div>
                  <table>
                    <thead>
                      <tr>
                        <th>name</th>
                        <th>total_spend</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td>Asha Verma</td>
                        <td>48210.50</td>
                      </tr>
                      <tr>
                        <td>Rohan Mehta</td>
                        <td>45990.00</td>
                      </tr>
                      <tr>
                        <td>Neha Iyer</td>
                        <td>40120.00</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
            <div className={styles.composer}>
              <div className={styles.chips}>
                <span>Orders this week by status</span>
                <span>Lowest stock by category</span>
              </div>
              <div className={styles.inputRow}>
                <span className={styles.fakeInput}>Ask in English or Hinglish</span>
                <span className={styles.send}>Ask</span>
              </div>
            </div>
          </div>
        </figure>
        </div>
        <div className={styles.heroFade} aria-hidden="true" />
      </section>

      <section className={styles.company}>
          <p>Built on a safety-first stack</p>
          <div className={styles.logos}>
          {STACK.map((item) => (
            <span key={item.name} title={item.name} aria-label={item.name}>
              <img src={item.logo} alt="" aria-hidden="true" />
              {item.badge ? <b>{item.badge}</b> : null}
              <em>{item.name}</em>
            </span>
          ))}
        </div>
      </section>

      <section className={styles.split}>
        <div className={styles.splitArt}>
          <div className={styles.artGlow} />
          <pre className={styles.codeCard}>
            <code>{`POST /api/query
{
  "session_id": "…",
  "question": "Top 5 customers
    by total spend last month"
}`}</code>
          </pre>
          <div className={styles.floatCard}>
            <span>Checked SQL</span>
            <strong>SELECT · JOIN · GROUP BY</strong>
            <em>Allowlist passed</em>
          </div>
        </div>
        <div className={styles.splitCopy}>
          <h2>Safety-checked SQL, tailored to your schema</h2>
          <p>
            Prompt text is not the security boundary. Every statement is parsed
            for the session dialect, checked against SchemaCatalog, and either
            executed read-only on demo — or returned unexecuted for custom DDL.
          </p>
          <Link className={styles.cta} to="/signin">
            Try for free
          </Link>
        </div>
      </section>

      <section className={styles.featuresHead}>
        <h2>Key features</h2>
        <p>The studio is the product. RAG stays on the server. No billing tiers in v1.</p>
      </section>

      <section className={styles.featureGrid}>
        <article>
          <div className={styles.featArt}>
            <span className={styles.orb} />
            <table>
              <tbody>
                <tr>
                  <td>name</td>
                  <td>48210</td>
                </tr>
                <tr>
                  <td>name</td>
                  <td>45990</td>
                </tr>
              </tbody>
            </table>
          </div>
          <h3>Live demo database</h3>
          <p>Eight-table Postgres e-commerce. Generate, check, EXPLAIN, execute read-only.</p>
        </article>
        <article>
          <div className={`${styles.featArt} ${styles.featLock}`}>
            <span className={styles.lock}>▣</span>
          </div>
          <h3>AST allowlist</h3>
          <p>Writes, DDL, and disallowed functions are rejected before anything can run.</p>
        </article>
        <article>
          <div className={styles.featArt}>
            <code>.sql</code>
            <small>Parsed, never executed</small>
          </div>
          <h3>Your own DDL</h3>
          <p>Postgres or MySQL, about 15 tables, 200 KB. Dialect locks after the first upload.</p>
        </article>
        <article>
          <div className={`${styles.featArt} ${styles.featLock}`}>
            <span className={styles.orb} />
            <small>pgvector · internal RAG</small>
          </div>
          <h3>Retrieval you never see</h3>
          <p>Examples are fetched from PostgreSQL embeddings. The UI only has ask and results.</p>
        </article>
      </section>

      <section className={styles.how}>
        <div>
          <h2>How it works</h2>
          <p>Three steps from landing to a checked query. Mode and dialect never go in the URL.</p>
          <div className={styles.accordion}>
            {STEPS.map((item, i) => (
              <button
                key={item.title}
                type="button"
                className={i === step ? styles.open : undefined}
                onClick={() => setStep(i)}
                aria-expanded={i === step}
              >
                <span>
                  {item.title}
                  {i === step ? <small>{item.body}</small> : null}
                </span>
                <i>{i === step ? "–" : "+"}</i>
              </button>
            ))}
          </div>
          <Link className={styles.cta} to="/signin">
            Try for free
          </Link>
        </div>
        <div className={styles.howArt}>
          <div className={styles.signCard}>
            <LogoMark className={styles.mark} />
            <p>Create your account</p>
            <span className={styles.fakeBtn}>Continue with Google</span>
            <span className={styles.fakeBtnSolid}>Sign in with email</span>
          </div>
        </div>
      </section>

      <section className={styles.ctaBand}>
        <h2>Ready to check your first query?</h2>
        <p>Verified account, then demo or your schema. 20 queries a day.</p>
        <Link className={styles.cta} to="/signin">
          Try for free
        </Link>
      </section>

      <section className={styles.faq}>
        <h2>Have questions?</h2>
        <div>
          {FAQS.map((item) => (
            <details key={item.q}>
              <summary>{item.q}</summary>
              <p>{item.a}</p>
            </details>
          ))}
        </div>
      </section>

      <Footer />
    </div>
  );
}
