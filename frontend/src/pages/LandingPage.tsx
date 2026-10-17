import { motion } from "framer-motion";
import { ArrowRight, Clock, Plane, ShieldCheck } from "lucide-react";
import { useEffect } from "react";
import { HeroTicket } from "../components/landing/HeroTicket";
import { SkyScene } from "../components/landing/SkyScene";
import { CityArrival } from "../components/landing/Vehicles";
import { DataSourcesStrip, GapSection, HowItWorks, HowWeDecide, MissionTicker } from "../components/landing/Sections";
import { HeroMissionBar } from "../components/mission/HeroMissionBar";
import { Button } from "../components/ui/Button";
import { usePlanMission } from "../hooks/useMission";

const ease = [0.22, 1, 0.36, 1] as const;

export function LandingPage() {
  const plan = usePlanMission();
  useEffect(() => {
    document.title = "TripMission — make sure you can actually make it";
  }, []);

  return (
    <>
      <section className="relative isolate overflow-hidden">
        <SkyScene />
        <div className="container-page grid items-center gap-12 pb-12 pt-12 sm:pt-16 lg:grid-cols-12 lg:gap-10 lg:pb-14 lg:pt-20">
          <div className="lg:col-span-7">
            <motion.p initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}
              className="glass inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-[12px] font-semibold uppercase tracking-[0.08em] text-ink shadow-sm">
              <span className="relative flex size-2">
                <span className="absolute inline-flex size-full rounded-full bg-coral animate-ping-soft" />
                <span className="relative inline-flex size-2 rounded-full bg-coral" />
              </span>
              For trips that have to work
            </motion.p>
            <motion.h1 initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, ease }}
              className="display mt-5 text-[44px] leading-[1.02] sm:text-[60px] lg:text-[72px]">
              Don't just plan the trip.
              <span className="text-gradient block pb-1 italic">Make sure you can actually make it.</span>
            </motion.h1>
            <motion.p initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.1, ease }}
              className="mt-6 max-w-xl text-[17px] leading-relaxed text-muted sm:text-[18px]">
              Turn a deadline, budget and destination into a complete journey that works in the real world — flight,
              train or bus, hotel and every transfer, costed all-in and checked against the minute you need to walk in.
            </motion.p>
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.2, ease }}
              className="mt-6 flex flex-wrap items-center gap-x-5 gap-y-2 text-[13.5px] font-medium text-fg/80">
              {([[Plane, "Live flights, trains & buses"], [Clock, "Door-to-venue timing"], [ShieldCheck, "Risk checked"]] as const).map(([Icon, t]) => (
                <span key={t} className="inline-flex items-center gap-1.5">
                  <Icon className="size-3.5 text-coral" aria-hidden />{t}
                </span>
              ))}
            </motion.div>
          </div>
          <div className="lg:col-span-5">
            <HeroTicket />
          </div>
          <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.3, ease }}
            className="lg:col-span-12">
            <HeroMissionBar />
          </motion.div>
        </div>
        <MissionTicker />
      </section>

      <GapSection />
      <HowItWorks />
      <HowWeDecide />
      <DataSourcesStrip />

      <section className="container-page py-16 sm:py-20">
        <motion.div initial={{ opacity: 0, y: 24, scale: 0.98 }} whileInView={{ opacity: 1, y: 0, scale: 1 }}
          viewport={{ once: true, margin: "-80px" }} transition={{ duration: 0.6, ease }}
          className="bg-sunset animate-gradient relative isolate overflow-hidden rounded-[28px] px-6 pb-60 pt-14 text-white shadow-[var(--shadow-lift)] sm:px-12">
          <span aria-hidden className="bg-stars absolute inset-0 -z-10 opacity-80 [mask-image:linear-gradient(90deg,#000_30%,transparent_70%)]" />
          {/* the sun, rising behind the button */}
          <span aria-hidden className="absolute -bottom-24 right-10 -z-10 size-56 rounded-full bg-sunrise/70 blur-2xl" />
          <div className="relative z-10 flex flex-col items-start justify-between gap-8 sm:flex-row sm:items-center">
            <div>
              <h2 className="display text-[34px] leading-tight !text-white sm:text-[44px]">Have somewhere to be?</h2>
              <p className="mt-2 text-[16px] text-white/80">It takes about a minute to set up a mission.</p>
            </div>
            <Button size="lg" variant="inverse" onClick={plan}>Plan a mission <ArrowRight className="size-4" aria-hidden /></Button>
          </div>

          <CityArrival />
        </motion.div>
      </section>
    </>
  );
}
