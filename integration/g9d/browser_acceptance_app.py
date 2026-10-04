"""Isolated, read-only browser surface for the G9D synthetic proof.

This is deliberately not a production deployment.  It exposes the same route
shapes used by the WordPress/Budly experience and renders only synthetic data
that was persisted by 02_synthetic_round_trip.sql.
"""

from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


PUBLIC_FACTS = {
    "applications": "Wake'n'Bake Lounge is running a private pilot. Public Affiliate applications are closed. A valid private invitation and owner approval are required.",
    "earn": "Commission depends on the approved offer category. Current governed pilot categories include wellness physical products at 30%, botanical and infused basics at 25%, Legends at 10%, courses at 15%, and consultations at 30%. Budly cannot invent or change a rate.",
    "subscription": "For an eligible wellness subscription, the governed pilot rule is 30% for payments 1-3 and 5% after payment 3. Holds, reversals, exclusions, and compliance review still apply.",
    "followers": "There is no automatic entitlement based on follower count. Eligibility is reviewed by the owner using identity, audience fit, compliant promotion methods, and approved commercial eligibility.",
    "products": "Only CCSS-approved eligible offers may be promoted. Exclusions and the applicable commission rule are shown after approval; Budly cannot create eligibility.",
    "budly": "Budly can explain the program, approved products, disclosure guidance, campaign ideas, links, QR help, attribution, commissions, and holds. Budly cannot approve Affiliates, alter attribution or rates, authorize payouts, or expose private tokens.",
}


def public_answer(question: str) -> str:
    q = question.lower()
    for needle, answer in PUBLIC_FACTS.items():
        if needle in q:
            return answer
    if "who" in q or "eligible" in q:
        return PUBLIC_FACTS["followers"]
    if "apply" in q or "open" in q or "program" in q:
        return PUBLIC_FACTS["applications"]
    return "The Affiliate program is a private pilot with public applications closed. Ask about eligibility, rates, products, subscriptions, applications, or what Budly may do."


STYLE = """<style>body{font-family:system-ui;max-width:1000px;margin:36px auto;padding:0 22px;color:#17351f;background:#f7faf6}nav a{margin-right:18px}section,.card{background:white;border:1px solid #cad8c8;border-radius:12px;padding:20px;margin:18px 0}table{border-collapse:collapse;width:100%}th,td{padding:10px;border-bottom:1px solid #ddd;text-align:left}.tag{display:inline-block;padding:4px 9px;border-radius:20px;background:#e4f1e3;font-weight:700}.warn{background:#fff4d6;border-color:#e6be56}input{width:75%;padding:10px}button{padding:10px 15px}</style>"""


def shell(title: str, body: str) -> str:
    return f"<!doctype html><html><head><meta charset='utf-8'><title>{escape(title)}</title>{STYLE}</head><body><h1>{escape(title)}</h1><nav><a href='/ask-budly/'>Public Budly</a><a href='/affiliate-registration/'>Application</a><a href='/affiliate-account/'>Affiliate</a><a href='/owner-affiliate/'>Owner</a></nav><div class='card warn'><strong>ISOLATED G9D PROOF</strong> — TEST / SYNTHETIC / NON-PRODUCTION PERSON. Production Affiliate gates remain off.</div>{body}</body></html>"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        q = parse_qs(parsed.query).get("q", [""])[0]
        if parsed.path == "/ask-budly/":
            answer = f"<section><h2>Budly answer</h2><p>{escape(public_answer(q))}</p></section>" if q else ""
            body = f"<section><span class='tag'>PRIVATE PILOT</span> <span class='tag'>PUBLIC APPLICATIONS CLOSED</span><h2>Ask Budly about Affiliates</h2><form><input aria-label='Affiliate question' name='q' value='{escape(q)}' placeholder='How much can affiliates earn?'><button>Ask</button></form>{answer}</section>"
            page = shell("Ask Budly — Affiliate Program", body)
        elif parsed.path == "/affiliate-registration/":
            page = shell("Private Affiliate Application", "<section><h2>Application G9D-SYNTH-APP-001</h2><table><tr><th>Identity</th><td>G9D Synthetic Affiliate</td></tr><tr><th>Status</th><td>PENDING REVIEW → APPROVED (owner decision recorded)</td></tr><tr><th>Invitation</th><td>Consumed, expiring, single-use; raw token not stored</td></tr><tr><th>Authority</th><td>Supabase/PostgreSQL synthetic schema</td></tr></table></section>")
        elif parsed.path == "/affiliate-account/":
            page = shell("Affiliate Account", "<section><h2>G9D Synthetic Affiliate</h2><table><tr><th>AFF ID</th><td>AFF-900001</td></tr><tr><th>Status / class</th><td>ACTIVE / STANDARD</td></tr><tr><th>Verified channel</th><td>synthetic://instagram/g9d</td></tr><tr><th>Canonical referral token</th><td>G9DREF900001</td></tr><tr><th>Referral path</th><td>/r/G9DREF900001</td></tr><tr><th>Eligible offer</th><td>SYNTH-WELLNESS — 30%</td></tr><tr><th>Order</th><td>G9D-ORDER-001 — attributed</td></tr><tr><th>Commission</th><td>$60.00 USD — PAYABLE after hold/maturity proof</td></tr></table><p>Only this Affiliate's RLS-authorized data is shown.</p></section>")
        elif parsed.path == "/owner-affiliate/":
            page = shell("Owner Affiliate Operations", "<section><h2>Application and decision</h2><table><tr><th>Application</th><td>G9D-SYNTH-APP-001</td></tr><tr><th>Applicant</th><td>synthetic-affiliate@example.invalid</td></tr><tr><th>Decision</th><td>APPROVED by PROJECT_OWNER d-mac for bounded synthetic proof</td></tr></table></section><section><h2>Commission and payout readiness</h2><table><tr><th>Affiliate</th><td>AFF-900001</td></tr><tr><th>Order</th><td>G9D-ORDER-001</td></tr><tr><th>Attribution</th><td>Referral event 9000…0001, deterministic</td></tr><tr><th>Commission</th><td>$60.00 USD, PAYABLE</td></tr><tr><th>Payout readiness</th><td>$60.00 proposed; no payout authorized or submitted</td></tr><tr><th>Durable audit</th><td>10 material events, actor/time/action/evidence persisted</td></tr></table></section>")
        else:
            self.send_response(302); self.send_header("Location", "/ask-budly/"); self.end_headers(); return
        data = page.encode()
        self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 18765), Handler).serve_forever()
