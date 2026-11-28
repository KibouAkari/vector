"use client";
import { useRef, useMemo, useEffect, useState } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { useInterfaceMotion } from "./use-interface-motion";
import { useWorld } from "./world-map";
function useTexture(world) {
  return useMemo(() => {
    if (!world || typeof document === "undefined") return null;
    const canvas = document.createElement("canvas");
    canvas.width = 2048;
    canvas.height = 1024;
    const context = canvas.getContext("2d");
    context.fillStyle = "#010204";
    context.fillRect(0, 0, 2048, 1024);
    context.fillStyle = "#17242a";
    context.strokeStyle = "#4a646b";
    context.lineWidth = 0.6;
    for (const country of world.features)
      for (const polygon of country.polygons) {
        context.beginPath();
        for (const ring of polygon) {
          ring.forEach(([lon, lat], index) => {
            const x = ((lon + 180) / 360) * 2048,
              y = ((90 - lat) / 180) * 1024;
            if (index === 0) context.moveTo(x, y);
            else context.lineTo(x, y);
          });
          context.closePath();
        }
        context.fill("evenodd");
        context.stroke();
      }
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    return texture;
  }, [world]);
}
function Earth({ clients, reduced, world }) {
  const group = useRef(),
    texture = useTexture(world);
  useEffect(() => () => texture?.dispose(), [texture]);
  useFrame((_, delta) => {
    if (!reduced && group.current) group.current.rotation.y += delta * 0.025;
  });
  const geometry = useMemo(() => {
    const positions = [];
    for (const row of clients) {
      const center = world?.features.find(
        (feature) => feature.id === row.country,
      )?.center;
      const latitude = Number.isFinite(row.latitude)
          ? row.latitude
          : center?.[1],
        longitude = Number.isFinite(row.longitude)
          ? row.longitude
          : center?.[0];
      if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) continue;
      const lat = (latitude * Math.PI) / 180,
        lon = (longitude * Math.PI) / 180;
      positions.push(
        1.012 * Math.cos(lat) * Math.cos(lon),
        1.012 * Math.sin(lat),
        1.012 * -Math.cos(lat) * Math.sin(lon),
      );
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute(
      "position",
      new THREE.Float32BufferAttribute(positions, 3),
    );
    return geometry;
  }, [clients, world]);
  useEffect(() => () => geometry.dispose(), [geometry]);
  return (
    <group ref={group} rotation={[0.12, -Math.PI / 2, 0]}>
      <mesh>
        <sphereGeometry args={[1, 64, 48]} />
        <meshStandardMaterial
          key={texture ? "geography-ready" : "geography-loading"}
          map={texture}
          color={texture ? "#c0cdd0" : "#10191f"}
          roughness={1}
          metalness={0.05}
        />
      </mesh>
      <mesh>
        <sphereGeometry args={[1.009, 36, 20]} />
        <meshBasicMaterial
          color="#9bbbc6"
          wireframe
          transparent
          opacity={0.025}
        />
      </mesh>
      <points geometry={geometry}>
        <pointsMaterial color="#e2f9fa" size={0.022} sizeAttenuation />
      </points>
    </group>
  );
}
export default function TrafficGlobe({
  clients = [],
  compact = false,
  dbip = false,
}) {
  const reduced = useInterfaceMotion(),
    world = useWorld();
  return (
    <div
      className={"ob-globe" + (compact ? " compact" : "")}
      role="group"
      aria-label="Earth with observed client countries. Country centres are approximate; unlocated traffic is not plotted."
    >
      <Canvas
        frameloop={reduced ? "demand" : "always"}
        camera={{ position: [0, 0.05, 2.65], fov: 46 }}
        dpr={[1, 1.5]}
        gl={{ antialias: true, powerPreference: "low-power", alpha: true }}
        fallback={<p>Use the country table to explore observed connections.</p>}
      >
        <ambientLight intensity={0.6} />
        <directionalLight
          position={[-3, 2, 4]}
          intensity={2.7}
          color="#d5e4ed"
        />
        <directionalLight
          position={[3, -1, -2]}
          intensity={0.35}
          color="#7496a1"
        />
        <Earth clients={clients} reduced={reduced} world={world} />
      </Canvas>
      {dbip && (
        <a
          className="ob-globe-attribution"
          href="https://db-ip.com"
          target="_blank"
          rel="noreferrer"
        >
          IP Geolocation by DB-IP
        </a>
      )}
    </div>
  );
}
