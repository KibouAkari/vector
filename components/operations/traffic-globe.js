"use client";
import { useRef, useMemo, useEffect } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { useReducedMotion } from "motion/react";
import * as THREE from "three";
function Earth({ clients, reduced }) {
  const group = useRef();
  useFrame((_, delta) => {
    if (!reduced && group.current) group.current.rotation.y += delta * 0.055;
  });
  const geometry = useMemo(() => {
    const positions = [];
    for (const row of clients) {
      if (!Number.isFinite(row.latitude) || !Number.isFinite(row.longitude))
        continue;
      const lat = (row.latitude * Math.PI) / 180,
        lon = (row.longitude * Math.PI) / 180;
      positions.push(
        1.015 * Math.cos(lat) * Math.sin(lon),
        1.015 * Math.sin(lat),
        1.015 * Math.cos(lat) * Math.cos(lon),
      );
    }
    const result = new THREE.BufferGeometry();
    result.setAttribute(
      "position",
      new THREE.Float32BufferAttribute(positions, 3),
    );
    return result;
  }, [clients]);
  useEffect(() => () => geometry.dispose(), [geometry]);
  return (
    <group ref={group} rotation={[0.15, -0.5, 0]}>
      <mesh>
        <sphereGeometry args={[1, 40, 24]} />
        <meshBasicMaterial
          color="#19323d"
          wireframe
          transparent
          opacity={0.38}
        />
      </mesh>
      <mesh>
        <sphereGeometry args={[0.995, 40, 24]} />
        <meshBasicMaterial color="#0b151c" />
      </mesh>
      <points geometry={geometry}>
        <pointsMaterial color="#a0e4e5" size={0.045} sizeAttenuation />
      </points>
    </group>
  );
}
export default function TrafficGlobe({ clients = [] }) {
  const reduced = useReducedMotion();
  return (
    <div
      className="op-globe"
      role="img"
      aria-label="Globe of observed client locations supplied by the collector. Unlocated clients are excluded."
    >
      <Canvas
        frameloop={reduced ? "demand" : "always"}
        camera={{ position: [0, 0, 2.8], fov: 48 }}
        dpr={[1, 1.5]}
        gl={{ antialias: true, powerPreference: "low-power" }}
        fallback={
          <p>
            Location view requires WebGL. All observations are available in the
            table.
          </p>
        }
      >
        <Earth clients={clients} reduced={reduced} />
      </Canvas>
      <span>Observed locations · 24 hours</span>
    </div>
  );
}
