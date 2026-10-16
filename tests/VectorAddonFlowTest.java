package com.kibouakari.vector;

import dcshadow.com.google.gson.Gson;
import dcshadow.com.google.gson.JsonObject;
import dcshadow.net.kyori.adventure.text.Component;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.charset.StandardCharsets;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.time.Instant;
import java.util.HexFormat;
import java.util.UUID;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

/** Records delivery; no Minecraft server, Discord token or external send. */
public final class VectorAddonFlowTest {
    static final UUID ONE = UUID.fromString("00000000-0000-0000-0000-000000000001");
    static final UUID TWO = UUID.fromString("00000000-0000-0000-0000-000000000002");
    static final class Captured implements VectorAddon.Bridge, AutoCloseable {
        final BlockingQueue<String> messages = new LinkedBlockingQueue<>();
        final AtomicInteger lookups = new AtomicInteger();
        final ExecutorService game = Executors.newSingleThreadExecutor(task -> new Thread(task, "captured-minecraft"));
        public void schedule(Runnable task) { game.execute(task); }
        public String playerName(UUID player) {
            checkThread(); lookups.incrementAndGet();
            return player.equals(ONE) ? "ExampleOne" : player.equals(TWO) ? "ExampleTwo" : null;
        }
        public void publish(String message) { checkThread(); messages.add(message); }
        static void checkThread() {
            if (!Thread.currentThread().getName().equals("captured-minecraft")) throw new AssertionError("Game access outside scheduled thread");
        }
        String take() throws Exception {
            String value = messages.poll(8, TimeUnit.SECONDS);
            if (value == null) throw new AssertionError("Captured reply missing");
            return value;
        }
        void silent(long milliseconds) throws Exception {
            if (messages.poll(milliseconds, TimeUnit.MILLISECONDS) != null) throw new AssertionError("Unexpected captured delivery");
        }
        public void close() throws Exception { game.shutdownNow(); game.awaitTermination(2, TimeUnit.SECONDS); }
    }

    static VectorAddon addon(Captured bridge, byte[] key, Path marker, boolean introduction) {
        VectorAddon addon = new VectorAddon();
        addon.start(bridge, key, marker, introduction);
        return addon;
    }

    static void chat(VectorAddon addon, UUID player, String message) {
        long start = System.nanoTime();
        if (addon.chat(Component.text(message), player)) throw new AssertionError("Normal forwarding cancelled");
        if (System.nanoTime() - start > TimeUnit.MILLISECONDS.toNanos(250)) throw new AssertionError("Chat callback blocked");
    }

    static void ready(byte[] key) throws Exception {
        JsonObject input = new JsonObject();
        input.addProperty("principal", ONE.toString()); input.addProperty("name", "ExampleOne");
        input.addProperty("event", ONE + ":999"); input.addProperty("message", "ordinary readiness probe");
        byte[] raw = new Gson().toJson(input).getBytes(StandardCharsets.UTF_8);
        HttpClient client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(1)).followRedirects(HttpClient.Redirect.NEVER).build();
        for (int i = 0; i < 25; i++) {
            try {
                String time = Long.toString(Instant.now().getEpochSecond());
                HttpRequest request = HttpRequest.newBuilder(URI.create("http://vector-fegcraft-assistant:8090/v1/minecraft"))
                    .timeout(Duration.ofSeconds(1)).header("X-Vector-Time", time)
                    .header("X-Vector-Signature", VectorAddon.sign(key, time, raw))
                    .POST(HttpRequest.BodyPublishers.ofByteArray(raw)).build();
                if (client.send(request, HttpResponse.BodyHandlers.ofString()).statusCode() == 200) return;
            } catch (Exception ignored) { }
            Thread.sleep(200);
        }
        throw new AssertionError("Isolated signed endpoint unavailable");
    }

    public static void main(String[] args) throws Exception {
        byte[] key = HexFormat.of().parseHex(Files.readString(Path.of(args[0])).strip());
        Path state = Path.of(args[1]), report = Path.of(args[2]);
        String phase = args[3];
        ready(key);
        JsonObject result = new JsonObject();
        result.addProperty("phase", phase);
        try (Captured bridge = new Captured()) {
            Path marker = state.resolve("intro.attempted");
            VectorAddon first = addon(bridge, key, marker, false);
            try {
                if (phase.equals("first")) {
                    chat(first, ONE, "wer hat die meisten Mobkills?");
                    bridge.silent(200);
                    if (bridge.lookups.get() != 0) throw new AssertionError("Ordinary chat consumed identity work");
                    chat(first, UUID.fromString("00000000-0000-0000-0000-000000000099"), "hey Vector, wer hat die meisten Mobkills?");
                    bridge.silent(200);
                    chat(first, ONE, "yoo Vector, wer hat die meisten Mobkills?");
                    String stats = bridge.take();
                    if (!stats.startsWith("Yoo ExampleOne,") || !stats.contains("ExampleTwo 52'000 Kills")) throw new AssertionError("Author or saved ranking mismatch");
                    chat(first, ONE, "hey Vector, was ist der seed?");
                    if (!bridge.take().contains("keine administrativen")) throw new AssertionError("Private topic boundary absent");
                    chat(first, ONE, "hallo Vector, welche Mods sind installiert?");
                    if (!bridge.take().contains("travelersbackpack")) throw new AssertionError("Mod inventory missing");
                    if (Files.exists(marker)) throw new AssertionError("Disabled introduction claimed delivery");
                } else if (phase.equals("restart")) {
                    chat(first, ONE, "hey Vector, wer hat die meisten Mobkills?");
                    bridge.silent(1200);
                } else throw new AssertionError("Unsupported phase");
            } finally { first.stop(); }

            VectorAddon announced = addon(bridge, key, marker, true);
            try {
                chat(announced, TWO, "hi Vector");
                String answer = bridge.take();
                if (phase.equals("first")) {
                    if (!answer.startsWith("Hey zusammen, ich bin Vector")) throw new AssertionError("Introduction capture absent");
                    answer = bridge.take();
                }
                if (!answer.startsWith("Hi ExampleTwo,")) throw new AssertionError("Authenticated author lost");
                bridge.silent(150);
            } finally { announced.stop(); }
            if (phase.equals("first")) {
                VectorAddon reloaded = addon(bridge, key, marker, true);
                try {
                    chat(reloaded, TWO, "hey Vector");
                    if (!bridge.take().startsWith("Hey ExampleTwo,")) throw new AssertionError("Introduction repeated after addon reload");
                    bridge.silent(150);
                } finally { reloaded.stop(); }
            }
            result.addProperty("passed", true);
            result.addProperty("forwarding_preserved", true);
            result.addProperty("identity_and_delivery_on_scheduled_thread", true);
            result.addProperty("ordinary_chat_ignored", true);
            result.addProperty("real_minecraft_callback_tested", false);
            result.addProperty("real_discord_delivery_tested", false);
            result.addProperty("external_messages_sent", 0);
            Files.writeString(report, new Gson().toJson(result));
            System.out.println("Captured addon transport phase passed: " + phase);
        }
    }
}
