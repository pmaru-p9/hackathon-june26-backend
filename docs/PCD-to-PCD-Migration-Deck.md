# PCD → PCD VM Migration — Slide Deck (content to paste into the template)

> **How to use:** Paste each slide's title + bullets into the Google template, keeping the
> template's layout/fonts. Apply the Platform9 palette below to titles/accents/diagrams.
> "Speaker notes" go in the notes pane. "Visual" describes the diagram to draw on that slide.

## Platform9 palette to apply
| Role | Hex | Use for |
|---|---|---|
| Primary blue | `#0A6CFF` | Slide titles, primary arrows, key headings |
| Deep navy | `#0B1F3A` | Body text, dark backgrounds, footer |
| Accent teal | `#19C2B3` | Highlights, "shared backend", success ticks |
| Amber | `#F5A623` | Caution / downtime window / "stop" step |
| Red | `#E5484D` | Failure / rollback paths |
| Green | `#16A34A` | "ACTIVE" / validated / completed |
| Light grey | `#F4F7FB` | Slide background / cards |
| Mid grey | `#64748B` | Captions, secondary text |

Fonts: keep the template's heading + body fonts.

---

## Slide 1 — Title
**PCD → PCD Virtual Machine Migration**
*Minimal-downtime, zero-copy VM moves across Private Cloud Director environments*

- Subtitle line: "vJailbreak-style migration, built for PCD → PCD on shared storage"
- Footer: Platform9 · Hackathon June '26

**Visual:** Two PCD environment "clouds" (SFO, LON) with a single VM gliding from left to right over a shared storage cylinder beneath both. Use primary blue clouds, teal storage.

**Speaker notes:** Goal — move a running VM from one PCD environment to another with near-zero downtime and no data copy, by handing over the volume that both environments already share.

---

## Slide 2 — The problem
**Moving a VM between two PCD environments today is painful**

- No native "migrate this VM to *another* PCD" action — it's a manual rebuild.
- Copying disks across environments is slow, error-prone, and means long downtime.
- Teams need to rebalance / consolidate / evacuate environments without disrupting workloads.
- Inspired by **vJailbreak** (VMware→PCD); we want the same one-click experience **PCD→PCD**.

**Visual:** A frustrated "manual" path: export image → copy GBs → recreate → reconfigure (lots of steps, red clock). Contrast arrow to the new way (next slide).

**Speaker notes:** Frame the pain: it's not that it's impossible, it's that it's manual and slow. The differentiator we exploit: in many fleets the two PCDs already sit on the *same* physical storage array.

---

## Slide 3 — The key idea
**If both environments share the storage, don't copy — hand over**

- Both PCDs mount the **same physical backend** (e.g. one NetApp array / NFS export).
- The disk already exists on storage both sides can see — so we **transfer ownership**, not bytes.
- Cinder gives us exactly this: **`unmanage`** (source forgets the volume) → **`manage`** (dest adopts it).
- Result: **zero data copy**, downtime measured in **seconds**, VM identity preserved.

**Visual:** One storage cylinder (teal) under two clouds. A "volume" tile on the array; an arrow flips its owner label from "SFO" to "LON". Big callout: **"0 bytes copied"**.

**Speaker notes:** This is the whole thesis. The volume file never moves. We only re-point which Cinder/Nova owns it, then re-create the VM on the destination from that same volume.

---

## Slide 4 — What we built
**A migration POD + a PCD-UI experience**

- **Migration POD** — runs in the *source* DU's namespace:
  - FastAPI REST API (`/api/v1/migrations`, `/destinations`), checkpointed job runner.
  - Kubernetes CRDs (`Migration`, `DestinationPCD`) + Secrets; packaged as a Helm chart.
- **PCD-UI** — admin-facing:
  - **Infrastructure → Destination PCD Envs** (register + test target environments).
  - **Migrations** sub-page (track jobs).
  - VM action **"Migrate to another PCD env"** → 5-step wizard.

**Visual:** Box diagram — Source DU (k8s) containing the Migration POD (API + Runner + CRDs); arrows to Source OpenStack APIs and to Destination OpenStack APIs; PCD-UI on top calling the POD via ingress.

**Speaker notes:** The POD lives next to the source cloud's control plane, talks OpenStack APIs on both sides, and is driven by the existing PCD-UI. Destinations are just OpenStack credentials — no extra kubeconfig needed.

---

## Slide 5 — Architecture at a glance
**Agentless, API-driven, checkpointed**

- **Source side:** Nova (stop/detach/delete/create), Cinder (unmanage/manage), Neutron (ports).
- **Destination side:** reached purely via OpenStack creds stored in a K8s Secret.
- **Shared backend resolver:** matches the source volume's export to the dest Cinder pool (via resmgr blueprint).
- **Checkpointed runner:** every phase records state in the `Migration` CR → resumable + auditable.

**Visual:** Layered diagram: PCD-UI → Ingress → POD (API → Runner → Engine) → {Source OS APIs | Dest OS APIs} → Shared storage array.

**Speaker notes:** Agentless = no software inside the guest. Everything is OpenStack API calls. The CR is the source of truth for progress and rollback.

---

## Slide 6 — The migration workflow (overview)
**Four stages, fully checkpointed**

1. **Preflight (P1–P9)** — non-mutating checks; blocks if anything's unsafe.
2. **Staging (S1)** — pre-create the destination network port (while VM still runs).
3. **Cutover (C1–C5)** — the brief downtime window.
4. **Verify (V1–V2)** — confirm the destination VM is ACTIVE; finalize.

**Visual:** Horizontal pipeline with 4 coloured segments (blue → blue → amber for cutover → green). Mark the **downtime window** spanning only the cutover segment.

**Speaker notes:** Only the cutover stage involves downtime. Preflight and staging happen with the VM still running; verify happens after it's back.

---

## Slide 7 — Cutover, step by step
**C1 → C5: stop, hand over the volume, recreate**

- **C1 Stop** source VM (quiesce the disk — clean, consistent bytes).
- **C2 Detach** data volumes; **C2b** read & temporarily clear `delete_on_termination`.
- **C2c Delete** source instance → frees the (boot) volume.
- **C3 Unmanage** volume(s) from the **source** Cinder.
- **C4 Manage** the same file on the **destination** Cinder (waits until `available`).
- **C5 Recreate** the VM on the destination from that volume — same IP/MAC/flavor/AZ.

**Visual:** Vertical timeline C1→C5 with the volume tile staying put on storage while the "owner" flips at C3→C4; VM icon disappears at C2c (source) and reappears at C5 (dest). Amber band = downtime.

**Speaker notes:** Boot-from-volume can't be detached, so we delete the source instance to free the root volume — preserving `delete_on_termination` so we never lose data. NetApp renames the backing file to the new volume UUID on manage; the engine handles that.

---

## Slide 8 — Why we stop the VM (consistency)
**A safe cold cutover — seconds, not minutes**

- We hand over the **same physical file** — it must be at rest (no in-flight writes).
- Stopping flushes the guest and guarantees a **single writer** during handover (no split-brain).
- Downtime = `stop → unmanage → manage → boot` — short, because **nothing is copied**.
- Trade-off chosen deliberately: a brief cold cutover vs. a true, lossless move.

**Visual:** A small clock over the amber cutover band labeled "downtime ≈ seconds". Side note: "zero-copy = short window".

**Speaker notes:** Zero-downtime would need live block mirroring (copying) — incompatible with reusing the same file in place. For shared-backend, the brief stop is the price of a safe, copy-free move.

---

## Slide 9 — Safety: rollback & auto-recovery
**Nothing is ever lost; failures self-heal**

- **Preflight gates** stop unsafe migrations before any change.
- **Regime A (pre-delete):** restore in place — reattach, restore the flag, power back on.
- **Regime B (post-delete):** reverse-migrate — re-manage the volume on the source, recreate the VM (now flavor- & filename-rename-aware) → falls back to **NeedsAttention** only as a backstop.
- **The volume file is never deleted** — only management ownership changes.

**Visual:** Decision diamond at the "point of no return" (C2c). Left branch = Regime A (green, in-place). Right branch = Regime B (teal, reverse) → backstop (amber).

**Speaker notes:** Every destructive run we did during testing recovered the VM automatically or via the documented path. Data on shared storage was never at risk.

---

## Slide 10 — Identity & config preserved
**The migrated VM is *the same* VM**

- **IP & MAC** preserved (re-created port on the destination network).
- **Flavor, AZ, security groups, key, metadata** carried over.
- **`delete_on_termination`** read, safely flipped during the move, restored on the destination.
- **`user_data` / cloud-init** preserved — so first-boot config (passwords, users, scripts) re-applies.
- Multi-volume VMs: **root + data** volumes handed over, re-attached at the right device paths.

**Visual:** "Before/After" card: same name, same IP, same MAC, same volumes — only the environment label changes (SFO → LON).

**Speaker notes:** Because a recreated VM gets a new instance-id, cloud-init re-runs; carrying user_data ensures the same password/config is re-applied (a real bug we found and fixed).

---

## Slide 11 — Validated end-to-end (live)
**Proven on real PCD environments + NetApp ONTAP NFS**

| Dimension | Status |
|---|---|
| Same-env (SFO→SFO) | ✅ cirros, ubuntu, multi-vol, user-data |
| **Cross-env (SFO→LON)** | ✅ single-vol, multi-vol, user-data |
| `delete_on_termination` true/false | ✅ preserved |
| IP / MAC / AZ preservation | ✅ |
| Rollback (A) + auto-recovery (B) | ✅ |

- Run through the **real product path**: CR → runner → preflight → cutover → verify.
- Key backend finding: **generic NFS can't `manage/unmanage`; NetApp ONTAP NFS can.**

**Visual:** Green check matrix (as above). Small badge: "PCD 2026.4, NetApp NFS, shared export 10.9.1.210:/cinder_nfs_vol1".

**Speaker notes:** We hit and fixed several real driver-level behaviors live (async manage, NetApp file rename, SDK arg order, root-volume detection, scheduler flaps). All covered by unit tests.

---

## Slide 12 — The user experience
**One action, a guided wizard**

- VM row → **⋮ → Other Actions → "Migrate to another PCD env"** (admins).
- 5-step wizard: **Destination → Cluster/AZ → Flavor → Networks → Review** (live preflight before launch).
- Track progress on the **Migrations** page; per-phase status from the CR.
- API also exposed via ingress (`/api/v1`) for automation.

**Visual:** Screenshot/mockup of the VM ⋮ menu showing the option, plus the 5-step wizard breadcrumb.

**Speaker notes:** It's wired into the existing VMs page and Infrastructure nav — no separate tool. Admin-gated because a cross-PCD move needs source admin.

---

## Slide 13 — Roadmap / next
**From hackathon to product**

- **Timing & downtime metrics** in the CR + UI (phase-wise duration, actual downtime).  *(in progress)*
- Optional **"no cloud-init churn"** mode (keep on-disk state untouched).
- **Batch migrations** (multiple VMs), scheduling, and progress dashboards.
- Broader backends (Ceph RBD, vendor iSCSI) — anything that supports `manage/unmanage`.
- Optional **copy-based** path for environments that *don't* share storage.

**Visual:** Simple "now → next → later" 3-column roadmap.

**Speaker notes:** The shared-backend handover is the fast path; a copy-based fallback would generalize it to non-shared environments (true vJailbreak parity).

---

## Slide 14 — Summary
**Zero-copy PCD → PCD migration, validated**

- Move a VM between PCD environments in **seconds**, **no data copy**, identity intact.
- **Agentless**, API-driven, checkpointed, with **safe rollback**.
- Built end-to-end: **POD + CRDs + Helm + PCD-UI wizard**, live-validated on NetApp.
- Same flow scales to cross-region and multi-volume workloads.

**Visual:** Recap of the single hero diagram (Slide 3) with a green "validated" stamp.

**Speaker notes:** Thank you — demo available on `test-du-…-sfo` (source) → LON (destination).
