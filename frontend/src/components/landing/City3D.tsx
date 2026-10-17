/**
 * The arrival scene in real 3D (three.js): a street at dawn with rows of buildings, street lamps and a car that
 * drives in once, trailing exhaust and switching the lamps on as it passes, then parks beside the "Arrived" pin.
 * Loaded lazily; calls `onFail` when WebGL isn't available so the flat version can take over.
 */
import { motion } from "framer-motion";
import { MapPin } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import * as THREE from "three";

const CAR_Z = 1.1;          // car lane (road spans z -2..4)
const LAMP_Z = -2.55;       // lamps stand on the far sidewalk
const DRIVE_SECONDS = 3.2;
const START_DELAY = 0.3;
const CAM = { y: 2.6, z: 19, fov: 30 };
const LOOK = new THREE.Vector3(0, 3.6, -4);

const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);

function seeded(seed: number) {
  let x = seed;
  return () => ((x = (x * 16807) % 2147483647) - 1) / 2147483646;
}

/** Facade texture: a grid of windows, some lit. Returns the colour map and a matching emissive (glow) map. */
function facadeTextures(seed: number) {
  const rnd = seeded(seed);
  const make = () => {
    const c = document.createElement("canvas");
    c.width = 64;
    c.height = 128;
    return c;
  };
  const color = make();
  const glow = make();
  const cc = color.getContext("2d")!;
  const gc = glow.getContext("2d")!;
  cc.fillStyle = "#1a2550";
  cc.fillRect(0, 0, 64, 128);
  gc.fillStyle = "#000";
  gc.fillRect(0, 0, 64, 128);
  for (let y = 0; y < 8; y++) {
    for (let x = 0; x < 4; x++) {
      const lit = rnd() < 0.32;
      cc.fillStyle = lit ? "#ffd38a" : "#0c1430";
      cc.fillRect(x * 16 + 4, y * 16 + 4, 8, 9);
      if (lit) {
        gc.fillStyle = rnd() < 0.5 ? "#ffb547" : "#ffd9a0";
        gc.fillRect(x * 16 + 4, y * 16 + 4, 8, 9);
      }
    }
  }
  const tex = (canvas: HTMLCanvasElement, srgb: boolean) => {
    const t = new THREE.CanvasTexture(canvas);
    t.wrapS = t.wrapT = THREE.RepeatWrapping;
    t.anisotropy = 4;
    if (srgb) t.colorSpace = THREE.SRGBColorSpace;
    return t;
  };
  return { map: tex(color, true), glow: tex(glow, true) };
}

/** Soft round sprite texture used for smoke and light pools. */
function radialTexture(inner: string, outer: string) {
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const g = c.getContext("2d")!;
  const grad = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  grad.addColorStop(0, inner);
  grad.addColorStop(1, outer);
  g.fillStyle = grad;
  g.fillRect(0, 0, 64, 64);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

function buildCar() {
  const car = new THREE.Group();
  const paint = new THREE.MeshPhysicalMaterial({ color: 0xf4f6fb, metalness: 0.35, roughness: 0.28, clearcoat: 1, clearcoatRoughness: 0.15 });
  const glass = new THREE.MeshPhysicalMaterial({ color: 0x0f1a36, metalness: 0.5, roughness: 0.08 });
  const rubber = new THREE.MeshStandardMaterial({ color: 0x15171c, roughness: 0.9 });
  const rim = new THREE.MeshStandardMaterial({ color: 0xb8c0cc, metalness: 0.9, roughness: 0.3 });

  // side profile, extruded across the car's width
  const body = new THREE.Shape();
  body.moveTo(-1.2, 0.22);
  body.lineTo(-1.2, 0.55);
  body.quadraticCurveTo(-1.18, 0.63, -1.0, 0.65);
  body.lineTo(-0.58, 0.67);
  body.lineTo(-0.26, 0.98);
  body.quadraticCurveTo(-0.2, 1.01, -0.1, 1.01);
  body.lineTo(0.42, 1.01);
  body.quadraticCurveTo(0.5, 1.0, 0.56, 0.95);
  body.lineTo(0.84, 0.67);
  body.lineTo(1.12, 0.61);
  body.quadraticCurveTo(1.24, 0.57, 1.24, 0.45);
  body.lineTo(1.24, 0.22);
  body.lineTo(-1.2, 0.22);
  const bodyGeo = new THREE.ExtrudeGeometry(body, { depth: 1.04, bevelEnabled: true, bevelSize: 0.04, bevelThickness: 0.05, bevelSegments: 3 });
  bodyGeo.translate(0, 0, -0.52);
  const shell = new THREE.Mesh(bodyGeo, paint);
  shell.castShadow = true;
  car.add(shell);

  const win = new THREE.Shape();
  win.moveTo(-0.47, 0.69);
  win.lineTo(-0.21, 0.94);
  win.lineTo(0.4, 0.94);
  win.lineTo(0.7, 0.69);
  win.lineTo(-0.47, 0.69);
  const winGeo = new THREE.ExtrudeGeometry(win, { depth: 1.16, bevelEnabled: false });
  winGeo.translate(0, 0, -0.58);
  car.add(new THREE.Mesh(winGeo, glass));
  const pillar = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.26, 1.17), paint);
  pillar.position.set(0.1, 0.81, 0);
  car.add(pillar);

  const wheels: THREE.Object3D[] = [];
  const tyreGeo = new THREE.CylinderGeometry(0.25, 0.25, 0.22, 28);
  tyreGeo.rotateX(Math.PI / 2);
  const rimGeo = new THREE.CylinderGeometry(0.15, 0.15, 0.23, 6);
  rimGeo.rotateX(Math.PI / 2);
  for (const x of [-0.74, 0.78]) {
    for (const z of [-0.5, 0.5]) {
      const w = new THREE.Group();
      const tyre = new THREE.Mesh(tyreGeo, rubber);
      tyre.castShadow = true;
      w.add(tyre, new THREE.Mesh(rimGeo, rim));
      w.position.set(x, 0.25, z);
      car.add(w);
      wheels.push(w);
    }
  }

  const head = new THREE.MeshStandardMaterial({ color: 0xfff4d6, emissive: 0xfff1c4, emissiveIntensity: 3 });
  const tail = new THREE.MeshStandardMaterial({ color: 0xff3b30, emissive: 0xff2a1f, emissiveIntensity: 2.5 });
  for (const z of [-0.36, 0.36]) {
    const h = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.08, 0.2), head);
    h.position.set(1.26, 0.48, z);
    const t = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.08, 0.22), tail);
    t.position.set(-1.23, 0.5, z);
    car.add(h, t);
  }

  // headlight beam on the road ahead
  const beam = new THREE.SpotLight(0xfff1d0, 30, 16, 0.42, 0.7, 1.4);
  beam.position.set(1.3, 0.5, 0);
  beam.target.position.set(7, 0, 0);
  car.add(beam, beam.target);

  // soft contact shadow so the car sits on the road
  const contact = new THREE.Mesh(
    new THREE.PlaneGeometry(2.9, 1.5),
    new THREE.MeshBasicMaterial({ map: radialTexture("rgba(0,0,0,0.55)", "rgba(0,0,0,0)"), transparent: true, depthWrite: false }),
  );
  contact.rotation.x = -Math.PI / 2;
  contact.position.y = 0.012;
  car.add(contact);

  return { car, wheels };
}

interface Lamp { x: number; light: THREE.PointLight; head: THREE.MeshStandardMaterial; cone: THREE.MeshBasicMaterial; pool: THREE.MeshBasicMaterial; level: number }

export default function City3D({ onFail }: { onFail: () => void }) {
  const host = useRef<HTMLDivElement>(null);
  const [pin, setPin] = useState<{ x: number; y: number } | null>(null);

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "low-power" });
    } catch {
      onFail();
      return;
    }
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.domElement.style.cssText = "display:block;width:100%;height:100%";
    el.prepend(renderer.domElement);

    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog(0x4a3260, 16, 52);
    const camera = new THREE.PerspectiveCamera(CAM.fov, 1, 0.1, 200);
    camera.position.set(0, CAM.y, CAM.z);
    camera.lookAt(LOOK);

    // ---- light: dusky sky fill + low warm sun from the right
    scene.add(new THREE.HemisphereLight(0x9fb4ff, 0x2a1a33, 1.1));
    const sun = new THREE.DirectionalLight(0xffa76b, 2.6);
    sun.position.set(26, 12, 14);
    sun.castShadow = true;
    sun.shadow.mapSize.set(1024, 512);
    Object.assign(sun.shadow.camera, { left: -32, right: 32, top: 16, bottom: -8, near: 1, far: 80 });
    sun.shadow.bias = -0.0005;
    sun.shadow.radius = 3;
    scene.add(sun);

    // ---- ground: road, lane markings, sidewalks, and the block behind
    const add = <T extends THREE.Object3D>(o: T) => (scene.add(o), o);
    const road = add(new THREE.Mesh(new THREE.PlaneGeometry(220, 6), new THREE.MeshStandardMaterial({ color: 0x23263b, roughness: 0.85, metalness: 0.05 })));
    road.rotation.x = -Math.PI / 2;
    road.position.z = 1;
    road.receiveShadow = true;
    const dash = new THREE.InstancedMesh(new THREE.PlaneGeometry(1.3, 0.12), new THREE.MeshStandardMaterial({ color: 0xe9e3d6, emissive: 0x5a5448, roughness: 0.6 }), 90);
    const m = new THREE.Matrix4();
    for (let i = 0; i < 90; i++) {
      m.makeRotationX(-Math.PI / 2).setPosition(-108 + i * 2.4, 0.01, 1);
      dash.setMatrixAt(i, m);
    }
    dash.receiveShadow = true;
    add(dash);
    const kerbMat = new THREE.MeshStandardMaterial({ color: 0x3a3d57, roughness: 0.9 });
    // far sidewalk (lamps stand here) and the near one, deep enough to run off the bottom of the frame
    for (const [z, depth] of [[-3, 2], [9, 10]]) {
      const walk = add(new THREE.Mesh(new THREE.BoxGeometry(220, 0.18, depth), kerbMat));
      walk.position.set(0, 0.09, z);
      walk.receiveShadow = true;
    }
    const block = add(new THREE.Mesh(new THREE.PlaneGeometry(220, 80), new THREE.MeshStandardMaterial({ color: 0x1b1d33, roughness: 1 })));
    block.rotation.x = -Math.PI / 2;
    block.position.set(0, 0.005, -44);
    block.receiveShadow = true;

    // ---- buildings: four rows, taller further back
    const rnd = seeded(7);
    const facades = [facadeTextures(11), facadeTextures(23), facadeTextures(37)];
    const roofMat = new THREE.MeshStandardMaterial({ color: 0x141a35, roughness: 0.95 });
    const facadeTone = [0xffffff, 0xd9dcef, 0xc4c8e4];
    const blinkers: THREE.MeshStandardMaterial[] = [];
    for (let row = 0; row < 4; row++) {
      const z0 = -5.6 - row * 6.5;
      for (let x = -70; x < 70;) {
        const w = 2.2 + rnd() * 2.8;
        const d = 2.6 + rnd() * 2.6;
        const h = 2.2 + row * 1.7 + rnd() * (2.4 + row * 1.6);
        const f = facades[Math.floor(rnd() * facades.length)];
        const face = (span: number) => {
          const map = f.map.clone();
          const glow = f.glow.clone();
          map.repeat.set(span / 2.2, h / 4.4);
          glow.repeat.copy(map.repeat);
          return new THREE.MeshStandardMaterial({ map, emissiveMap: glow, emissive: 0xffffff, emissiveIntensity: 1.4,
            color: facadeTone[row % 3], roughness: 0.75, metalness: 0.1 });
        };
        const side = face(d);
        const front = face(w);
        const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), [side, side, roofMat, roofMat, front, front]);
        mesh.position.set(x + w / 2, h / 2, z0 - d / 2);
        mesh.castShadow = mesh.receiveShadow = true;
        add(mesh);
        // rooftop clutter and the odd antenna with a blinking warning light
        if (rnd() < 0.45) {
          const unit = add(new THREE.Mesh(new THREE.BoxGeometry(0.6 + rnd() * 0.6, 0.4, 0.6 + rnd() * 0.6), roofMat));
          unit.position.set(x + w / 2 + (rnd() - 0.5) * w * 0.4, h + 0.2, z0 - d / 2);
          unit.castShadow = true;
        }
        if (row >= 1 && rnd() < 0.12) {
          const mast = add(new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 1.6), roofMat));
          mast.position.set(x + w / 2, h + 0.8, z0 - d / 2);
          const red = new THREE.MeshStandardMaterial({ color: 0xff3b30, emissive: 0xff2a1f, emissiveIntensity: 2 });
          const bulb = add(new THREE.Mesh(new THREE.SphereGeometry(0.07, 10, 8), red));
          bulb.position.set(x + w / 2, h + 1.62, z0 - d / 2);
          blinkers.push(red);
        }
        x += w + 0.3 + rnd() * 0.9;
      }
    }

    // ---- street lamps on the far sidewalk; each has a real point light, a glowing head, a light cone and a pool
    const metal = new THREE.MeshStandardMaterial({ color: 0x8a92a6, metalness: 0.8, roughness: 0.35 });
    const poolTex = radialTexture("rgba(255,190,110,0.9)", "rgba(255,190,110,0)");
    const lamps: Lamp[] = [];
    for (let x = -36; x <= 36; x += 6) {
      const pole = add(new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.07, 3.4, 10), metal));
      pole.position.set(x, 1.8, LAMP_Z);
      pole.castShadow = true;
      const arm = add(new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.06, 0.95), metal));
      arm.position.set(x, 3.48, LAMP_Z + 0.45);
      const headMat = new THREE.MeshStandardMaterial({ color: 0x3b3f52, emissive: 0xffb547, emissiveIntensity: 0 });
      const head = add(new THREE.Mesh(new THREE.BoxGeometry(0.34, 0.1, 0.5), headMat));
      head.position.set(x, 3.42, LAMP_Z + 0.9);
      const light = new THREE.PointLight(0xffb05a, 0, 9, 1.8);
      light.position.set(x, 3.2, LAMP_Z + 0.9);
      add(light);
      const coneMat = new THREE.MeshBasicMaterial({ color: 0xffb547, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide });
      const cone = add(new THREE.Mesh(new THREE.ConeGeometry(1.15, 3.3, 24, 1, true), coneMat));
      cone.position.set(x, 1.72, LAMP_Z + 0.9);
      const poolMat = new THREE.MeshBasicMaterial({ map: poolTex, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false });
      const pool = add(new THREE.Mesh(new THREE.PlaneGeometry(3.4, 3.4), poolMat));
      pool.rotation.x = -Math.PI / 2;
      pool.position.set(x, 0.2, LAMP_Z + 0.9);
      lamps.push({ x, light, head: headMat, cone: coneMat, pool: poolMat, level: 0 });
    }

    // ---- the car, and a pool of smoke sprites that trail behind it
    const { car, wheels } = buildCar();
    car.position.z = CAR_Z;
    add(car);
    const smokeTex = radialTexture("rgba(230,232,240,0.9)", "rgba(230,232,240,0)");
    const puffs = Array.from({ length: 36 }, () => {
      const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: smokeTex, transparent: true, opacity: 0, depthWrite: false }));
      s.visible = false;
      add(s);
      return { s, age: 0, life: 1, drift: new THREE.Vector3() };
    });
    let nextPuff = 0;
    let spawnTimer = 0;

    // ---- sizing: the route spans what the camera can see across the car's lane
    let startX = -10;
    let endX = 10;
    const pinPoint = new THREE.Vector3();
    const project = () => {
      pinPoint.set(endX + 1.95, 0.2, CAR_Z).project(camera);
      setPin({ x: (pinPoint.x * 0.5 + 0.5) * el.clientWidth, y: (-pinPoint.y * 0.5 + 0.5) * el.clientHeight });
    };
    const layout = () => {
      const w = el.clientWidth;
      const h = el.clientHeight;
      if (!w || !h) return;
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      const half = (CAM.z - CAR_Z) * Math.tan(THREE.MathUtils.degToRad(CAM.fov / 2)) * camera.aspect;
      startX = -half + 1.7;
      endX = half - (w < 640 ? 2.9 : 4.4);
      if (state === "arrived") {
        car.position.x = endX;
        project();
      }
    };

    // ---- run: render only while on screen; drive once when the street is mostly in view
    let state: "waiting" | "driving" | "arrived" = reduced ? "arrived" : "waiting";
    // exposes the drive phase on the element (useful for tests and debugging)
    const mark = (phase: typeof state) => { el.dataset.state = phase; };
    let driven = 0; // seconds of drive actually rendered; frame-stepped so a slow frame pauses rather than skips
    let visible = false;
    let frame = 0;
    let last = performance.now();
    const mouse = { x: 0, y: 0 };
    const onMove = (e: PointerEvent) => {
      const r = el.getBoundingClientRect();
      mouse.x = THREE.MathUtils.clamp(((e.clientX - r.left) / r.width) * 2 - 1, -1, 1);
      mouse.y = THREE.MathUtils.clamp(((e.clientY - r.top) / r.height) * 2 - 1, -1, 1);
    };
    if (!reduced) window.addEventListener("pointermove", onMove, { passive: true });

    const io = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      if (visible && state === "waiting" && entry.intersectionRatio >= 0.6) {
        state = "driving";
        mark(state);
      }
      if (visible && !frame) {
        last = performance.now();
        frame = requestAnimationFrame(tick);
      }
    }, { threshold: [0, 0.6] });
    // warm up the shaders while the banner is still off screen so its first appearance doesn't stall; the drive
    // never waits on this (some drivers report compile completion late or not at all)
    let disposed = false;
    renderer.compileAsync(scene, camera).then(() => !disposed && renderer.render(scene, camera), () => undefined);
    io.observe(el);
    const ro = new ResizeObserver(layout);
    ro.observe(el);
    mark(state);
    layout();
    car.position.x = state === "arrived" ? endX : startX;
    if (state === "arrived") project();

    function tick() {
      frame = 0;
      if (!visible) return;
      const now = performance.now();
      const dt = Math.min((now - last) / 1000, 0.05);
      last = now;
      const t = now / 1000;

      if (state === "driving") {
        driven += dt;
        const p = THREE.MathUtils.clamp((driven - START_DELAY) / DRIVE_SECONDS, 0, 1);
        const prev = car.position.x;
        car.position.x = startX + (endX - startX) * easeOut(p);
        const moved = car.position.x - prev;
        for (const w of wheels) w.rotation.z -= moved / 0.25;
        spawnTimer -= dt;
        if (p > 0 && p < 0.97 && spawnTimer <= 0) {
          spawnTimer = 0.045;
          const puff = puffs[nextPuff++ % puffs.length];
          puff.age = 0;
          puff.life = 1.1 + Math.random() * 0.5;
          puff.drift.set(-0.5 - Math.random() * 0.5, 0.45 + Math.random() * 0.35, (Math.random() - 0.5) * 0.4);
          puff.s.position.set(car.position.x - 1.3, 0.3, CAR_Z + 0.35);
          puff.s.visible = true;
        }
        if (p >= 1) {
          state = "arrived";
          mark(state);
          project();
        }
      } else {
        car.position.x = state === "arrived" ? endX : startX;
      }

      for (const puff of puffs) {
        if (!puff.s.visible) continue;
        puff.age += dt;
        const k = puff.age / puff.life;
        if (k >= 1) {
          puff.s.visible = false;
          continue;
        }
        puff.s.position.addScaledVector(puff.drift, dt);
        puff.s.scale.setScalar(0.5 + k * 2.6);
        (puff.s.material as THREE.SpriteMaterial).opacity = 0.72 * (1 - k);
      }

      for (const lamp of lamps) {
        const on = state === "arrived" || (state === "driving" && car.position.x >= lamp.x - 0.6);
        lamp.level += ((on ? 1 : 0) - lamp.level) * Math.min(1, dt * 5);
        lamp.light.intensity = 26 * lamp.level;
        lamp.head.emissiveIntensity = 3.2 * lamp.level;
        lamp.cone.opacity = 0.07 * lamp.level;
        lamp.pool.opacity = 0.55 * lamp.level;
      }
      for (const b of blinkers) b.emissiveIntensity = Math.sin(t * 3) > 0.55 ? 3 : 0.2;

      // gentle parallax towards the pointer
      camera.position.x += (mouse.x * 1.4 - camera.position.x) * Math.min(1, dt * 2.5);
      camera.position.y += (CAM.y - mouse.y * 0.45 - camera.position.y) * Math.min(1, dt * 2.5);
      camera.lookAt(LOOK);

      renderer.render(scene, camera);
      frame = requestAnimationFrame(tick);
    }

    return () => {
      disposed = true;
      cancelAnimationFrame(frame);
      io.disconnect();
      ro.disconnect();
      window.removeEventListener("pointermove", onMove);
      scene.traverse((o) => {
        const mesh = o as THREE.Mesh;
        mesh.geometry?.dispose();
        const mats = Array.isArray(mesh.material) ? mesh.material : mesh.material ? [mesh.material] : [];
        for (const mat of mats) {
          for (const v of Object.values(mat)) if (v instanceof THREE.Texture) v.dispose();
          mat.dispose();
        }
      });
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, [onFail]);

  return (
    // the street fills the lower part of the banner and fades into the sky, leaving the copy on open sky
    <div ref={host} aria-hidden className="absolute inset-x-0 bottom-0 h-[62%] [mask-image:linear-gradient(to_top,#000_72%,transparent)]">
      {pin && (
        <motion.span className="absolute flex -translate-x-1/2 -translate-y-full flex-col items-center"
          style={{ left: pin.x, top: pin.y }}
          initial={false} animate={{ opacity: [0, 1], y: [-26, 0] }} transition={{ type: "spring", stiffness: 260, damping: 12 }}>
          <span className="mb-1 rounded-full bg-white px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-[0.08em] text-night">Arrived</span>
          <MapPin className="size-8 fill-sunrise text-white drop-shadow" strokeWidth={1.6} />
        </motion.span>
      )}
    </div>
  );
}
