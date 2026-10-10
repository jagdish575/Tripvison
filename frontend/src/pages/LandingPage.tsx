import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import { useEffect } from "react";
import { HeroTicket } from "../components/landing/HeroTicket";
import { DataSourcesStrip, GapSection, HowItWorks, HowWeDecide } from "../components/landing/Sections";
import { HeroMissionBar } from "../components/mission/HeroMissionBar";
import { Button } from "../components/ui/Button";
import { usePlanMission } from "../hooks/useMission";

export function LandingPage() {
  const plan = usePlanMission();
  useEffect(() => {
    document.title = "TripMission — make sure you can actually make it";
  }, []);

  return (
    <>
      <section className="relative">
        <div className="container-page grid items-center gap-12 pb-12 pt-12 sm:pt-16 lg:grid-cols-12 lg:gap-10 lg:pb-14 lg:pt-20">
          <div className="lg:col-span-7">
            <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.4 }} className="eyebrow">
              For trips that have to work
            </motion.p>
            <motion.h1 initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
              className="display mt-4 text-[44px] leading-[1.02] sm:text-[60px] lg:text-[68px]">
              Don't just plan the trip.
              <span className="block italic text-muted">Make sure you can actually make it.</span>
            </motion.h1>
            <motion.p initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.08 }}
              className="mt-6 max-w-xl text-[17px] leading-relaxed text-muted sm:text-[18px]">
              Turn a deadline, budget and destination into a complete journey that works in the real world — flight,
              train or bus, hotel and every transfer, costed all-in and checked against the minute you need to walk in.
            </motion.p>
          </div>
          <div className="lg:col-span-5">
            <HeroTicket />
          </div>
          <div className="lg:col-span-12">
            <HeroMissionBar />
          </div>
        </div>
      </section>

      <GapSection />
      <HowItWorks />
      <HowWeDecide />
      <DataSourcesStrip />

      <section className="bg-paper">
        <div className="container-page flex flex-col items-start justify-between gap-6 py-16 sm:flex-row sm:items-center">
          <div>
            <h2 className="display text-[32px] leading-tight">Have somewhere to be?</h2>
            <p className="mt-2 text-muted">It takes about a minute to set up a mission.</p>
          </div>
          <Button size="lg" onClick={plan}>Plan a mission <ArrowRight className="size-4" aria-hidden /></Button>
        </div>
      </section>
    </>
  );
}
