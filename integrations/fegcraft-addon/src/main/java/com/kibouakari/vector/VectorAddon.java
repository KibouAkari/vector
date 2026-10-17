package com.kibouakari.vector;

import dcshadow.com.google.gson.Gson;
import dcshadow.com.google.gson.JsonObject;
import dcshadow.net.kyori.adventure.text.Component;
import dcshadow.net.kyori.adventure.text.TextComponent;
import dcshadow.net.kyori.adventure.text.format.TextColor;
import dcshadow.net.kyori.adventure.key.Key;
import dcshadow.net.kyori.adventure.text.object.ObjectContents;
import de.erdbeerbaerlp.dcintegration.common.DiscordIntegration;
import de.erdbeerbaerlp.dcintegration.common.addon.DiscordIntegrationAddon;
import de.erdbeerbaerlp.dcintegration.common.api.DiscordEventHandler;
import de.erdbeerbaerlp.dcintegration.common.storage.Configuration;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.io.InputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.lang.reflect.Method;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.time.Duration;
import java.time.Instant;
import java.util.HexFormat;
import java.util.Properties;
import java.util.UUID;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionStage;
import java.util.concurrent.Flow;
import java.util.concurrent.RejectedExecutionException;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.logging.Logger;
import java.util.regex.Pattern;

/** Uses only the installed bridge. No Discord listener or Minecraft commands. */
public final class VectorAddon implements DiscordIntegrationAddon {
    private static final Logger LOG = Logger.getLogger("VectorMinecraft");
    private static final Pattern GREETING = Pattern.compile("^\\s*(hi|hey|hallo|yo{1,3}|hoi|huhu|hello)\\s+vector(?:\\s*[,!:?]\\s*|\\s+|$)", Pattern.CASE_INSENSITIVE);
    private static final Pattern UNSAFE = Pattern.compile("[/\\\\](give|op|deop|execute|gamemode|tp|teleport|seed|summon|kill|setblock|fill|sudo|bin|etc|opt)\\b|\\b(seed|passwort|password|api.?key|token|rcon|docker|curl|wget|bash|powershell|cheat|gamemode)\\b|https?://|www\\.|@|`|[<>\\x00-\\x1f\\x7f]|\\u00a7", Pattern.CASE_INSENSITIVE);
    private static final URI ENDPOINT = URI.create("http://vector-fegcraft-assistant:8090/v1/minecraft");
    private static final String INTRO = "Hey zusammen, ich bin Vector, euer neuer Minecraft-Assistent! Ich helfe bei Fragen und Problemen rund um Minecraft und zeige euch Statistiken und Rekorde. Beginnt eure Nachricht einfach mit Hey Vector oder Yoo Vector.";
    private final String session = UUID.randomUUID().toString();
    private final AtomicLong sequence = new AtomicLong();
    private final Gson gson = new Gson();
    private volatile ThreadPoolExecutor worker;
    private final AtomicBoolean requestInFlight = new AtomicBoolean();
    private volatile boolean active;
    private DiscordEventHandler handler;
    private byte[] key;
    interface Bridge {
        void schedule(Runnable task) throws Exception;
        String playerName(UUID player);
        void publish(String message);
    }
    private Bridge bridge;
    private Path introMarker;
    private boolean introduction;
    private String avatar = "";
    private boolean logo;

    /** Fixed local texture only; no fake player identity or profile lookup. */
    static Component presentation(String message, boolean logo) {
        Component result = Component.empty();
        if (logo) result = result.append(Component.object(ObjectContents.playerHead()
            .texture(Key.key("vector:entity/vector")).hat(false).build())).append(Component.space());
        return result.append(Component.text("<Vector> ", TextColor.color(0x8de0b7)))
            .append(Component.text(message, TextColor.color(0xf0f7f3)));
    }
    private final HttpClient client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).followRedirects(HttpClient.Redirect.NEVER)
        .proxy(new java.net.ProxySelector() {
            public List<java.net.Proxy> select(URI uri) { return List.of(java.net.Proxy.NO_PROXY); }
            public void connectFailed(URI uri, java.net.SocketAddress address, IOException error) { }
        }).build();

    @Override
    public void load(DiscordIntegration dc) {
        Path directory = DiscordIntegration.discordDataDir.toPath().resolve("vector");
        Path config = directory.resolve("bridge.properties");
        if (!Files.isRegularFile(config, LinkOption.NOFOLLOW_LINKS)) {
            LOG.info("Vector bridge disabled: configuration absent.");
            return;
        }
        try {
            Properties properties = new Properties();
            try (InputStream stream = Files.newInputStream(config, LinkOption.NOFOLLOW_LINKS)) {
                properties.load(stream);
            }
            if (!"true".equals(properties.getProperty("enabled", "false"))) return;
            Path token = Path.of(properties.getProperty("tokenFile", "/run/secrets/vector_fegcraft_token"));
            if (!Files.isRegularFile(token, LinkOption.NOFOLLOW_LINKS) || Files.size(token) > 128) throw new IllegalArgumentException();
            String secret;
            try (InputStream stream = Files.newInputStream(token, LinkOption.NOFOLLOW_LINKS)) {
                secret = new String(stream.readNBytes(129), StandardCharsets.US_ASCII).strip();
            }
            if (!secret.matches("[a-f0-9]{64}")) throw new IllegalArgumentException();
            key = HexFormat.of().parseHex(secret);
            // Fixed inspected 26.2 integration field; reflection avoids bundling
            // Minecraft classes and still schedules all game access on its thread.
            Object minecraft = Class.forName("de.erdbeerbaerlp.dcintegration.architectury.DiscordIntegrationMod").getField("server").get(null);
            Method execute = minecraft.getClass().getMethod("execute", Runnable.class);
            introMarker = directory.resolve("introduction-v1.attempted");
            introduction = "true".equals(properties.getProperty("introductionEnabled", "false"));
            avatar = properties.getProperty("avatarUrl", "");
            if (!avatar.isEmpty() && !avatar.matches("https://[A-Za-z0-9./_-]{1,240}\\.png")) throw new IllegalArgumentException();
            String texture = properties.getProperty("logoTexture", "");
            if (!texture.isEmpty() && !texture.equals("vector:entity/vector")) throw new IllegalArgumentException();
            logo = !texture.isEmpty();
            if (!avatar.isEmpty() && !Configuration.instance().webhook.enable) throw new IllegalArgumentException();
            start(new Bridge() {
                public void schedule(Runnable task) throws Exception { execute.invoke(minecraft, task); }
                public String playerName(UUID player) { return dc.getServerInterface().getPlayers().get(player); }
                public void publish(String message) {
                    dc.getServerInterface().sendIngameMessage(presentation(message, logo));
                    // System output is not a player hook; forward exactly once.
                    dc.sendMessage("Vector", message, dc.getChannel(Configuration.instance().advanced.chatOutputChannelID), avatar);
                }
            }, key, introMarker, introduction);
            handler = new DiscordEventHandler() {
                @Override
                public boolean onMinecraftMessage(Component message, UUID player) {
                    return chat(message, player);
                }
            };
            dc.registerEventHandler(handler);
            LOG.info("Vector Minecraft bridge registered; no Discord listener.");
        } catch (Exception failure) {
            active = false;
            if (worker != null) worker.shutdownNow();
            LOG.warning("Vector bridge initialization failed; no secret details logged.");
        }
    }

    boolean chat(Component message, UUID player) {
        receive(message, player);
        return false; // Preserve normal chat/Discord forwarding.
    }

    void start(Bridge transport, byte[] secret, Path marker, boolean intro) {
        if (active || secret.length != 32) throw new IllegalArgumentException();
        bridge = transport;
        key = secret.clone();
        introMarker = marker;
        introduction = intro;
        worker = new ThreadPoolExecutor(1, 1, 0, TimeUnit.SECONDS, new ArrayBlockingQueue<>(1), task -> {
            Thread thread = new Thread(task, "Vector-local-chat");
            thread.setDaemon(true);
            return thread;
        });
        active = true;
    }

    private static void text(Component component, StringBuilder out, int depth) {
        if (depth > 20 || out.length() > 1200) throw new IllegalArgumentException();
        if (component instanceof TextComponent plain) out.append(plain.content());
        else throw new IllegalArgumentException();
        for (Component child : component.children()) text(child, out, depth + 1);
    }

    void receive(Component component, UUID player) {
        if (!active) return;
        try {
            StringBuilder plain = new StringBuilder();
            text(component, plain, 0);
            String message = plain.toString();
            if (message.length() > 1200 || !GREETING.matcher(message).find()) return;
            // Callback may originate on a chat thread. Resolve identity and submit
            // work on the server thread; never call a profile/network resolver.
            onServer(() -> {
                if (!active) return;
                String name = bridge.playerName(player);
                if (name == null || !name.matches("[A-Za-z0-9_]{1,16}")) return;
                JsonObject request = new JsonObject();
                request.addProperty("principal", player.toString());
                request.addProperty("name", name);
                request.addProperty("event", session + ":" + sequence.incrementAndGet());
                request.addProperty("message", message);
                if (!requestInFlight.compareAndSet(false, true)) return;
                try {
                    worker.execute(() -> {
                        String reply;
                        try { reply = answer(request); }
                        finally { requestInFlight.set(false); }
                        // Admission reopens before delivery is visible. The single
                        // queue slot covers completion handoff, never HTTP backlog.
                        if (reply != null) onServer(() -> {
                            if (!active) return;
                            introduce();
                            bridge.publish(reply);
                        });
                    });
                } catch (RejectedExecutionException ignored) {
                    requestInFlight.set(false);
                    // No unbounded queue, public busy-message spam or tick delay.
                }
            });
        } catch (Exception ignored) { }
    }

    private void onServer(Runnable task) {
        try {
            bridge.schedule(task);
        } catch (Exception failure) {
            LOG.warning("Vector server-thread scheduling unavailable.");
        }
    }

    static String sign(byte[] key, String timestamp, byte[] body) throws Exception {
        Mac mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(key, "HmacSHA256"));
        mac.update((timestamp + "\n").getBytes(StandardCharsets.US_ASCII));
        return HexFormat.of().formatHex(mac.doFinal(body));
    }

    static boolean safe(String value) {
        if (value == null || value.isBlank() || value.length() > 420 || UNSAFE.matcher(value).find()) return false;
        return value.codePoints().noneMatch(c -> c > 0xffff || c >= 0x200b && c <= 0x200f || c >= 0x2028 && c <= 0x202f || c >= 0x2600 && c <= 0x27ff);
    }

    static final class LimitedBody implements HttpResponse.BodySubscriber<byte[]> {
        private final CompletableFuture<byte[]> result = new CompletableFuture<>();
        private final ByteArrayOutputStream body = new ByteArrayOutputStream();
        private volatile Flow.Subscription subscription;
        private volatile boolean aborted;
        public CompletionStage<byte[]> getBody() { return result; }
        public void onSubscribe(Flow.Subscription value) {
            subscription = value;
            if (aborted) value.cancel(); else value.request(Long.MAX_VALUE);
        }
        void abort() {
            aborted = true;
            if (subscription != null) subscription.cancel();
            result.completeExceptionally(new IOException("REQUEST_CANCELLED"));
        }
        public void onNext(List<ByteBuffer> buffers) {
            for (ByteBuffer buffer : buffers) {
                if (body.size() + buffer.remaining() > 8192) {
                    subscription.cancel();
                    result.completeExceptionally(new IOException("RESPONSE_LIMIT"));
                    return;
                }
                byte[] chunk = new byte[buffer.remaining()];
                buffer.get(chunk);
                body.writeBytes(chunk);
            }
        }
        public void onError(Throwable failure) { result.completeExceptionally(failure); }
        public void onComplete() { result.complete(body.toByteArray()); }
    }

    private String answer(JsonObject payload) {
        try {
            byte[] body = gson.toJson(payload).getBytes(StandardCharsets.UTF_8);
            String timestamp = Long.toString(Instant.now().getEpochSecond());
            HttpRequest request = HttpRequest.newBuilder(ENDPOINT).timeout(Duration.ofSeconds(27))
                .header("Content-Type", "application/json").header("X-Vector-Time", timestamp)
                .header("X-Vector-Signature", sign(key, timestamp, body))
                .POST(HttpRequest.BodyPublishers.ofByteArray(body)).build();
            // Explicit wall deadline includes a slow/dribbling response body;
            // HttpRequest timeout alone can stop covering after headers arrive.
            LimitedBody subscriber = new LimitedBody();
            CompletableFuture<HttpResponse<byte[]>> future = client.sendAsync(request, ignored -> subscriber);
            HttpResponse<byte[]> response;
            try {
                response = future.get(27, TimeUnit.SECONDS);
            } catch (Exception failure) {
                subscriber.abort();
                future.cancel(true);
                throw failure;
            }
            byte[] raw = response.body();
            if (response.statusCode() != 200 || raw.length > 8192) return null;
            JsonObject result = gson.fromJson(new String(raw, StandardCharsets.UTF_8), JsonObject.class);
            if (!result.has("status") || !"answered".equals(result.get("status").getAsString()) || !result.has("text")) return null;
            String reply = result.get("text").getAsString();
            return safe(reply) ? reply : null;
        } catch (Exception ignored) {
            LOG.warning("Vector local request unavailable; no cloud fallback.");
            return null;
        }
    }

    private void introduce() {
        if (!introduction) return;
        try {
            // Claim BEFORE either delivery. Existing/uncertain attempts are never
            // retried on reload/restart. Operator review can inspect this marker.
            if (claimIntroduction(introMarker)) bridge.publish(INTRO);
        } catch (Exception ignored) {
            LOG.warning("Vector introduction not retried; delivery state requires review.");
        }
    }

    static boolean claimIntroduction(Path path) throws IOException {
        try (FileChannel marker = FileChannel.open(path, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE)) {
            marker.write(StandardCharsets.UTF_8.encode("attempted; delivery acknowledgement unavailable\n"));
            marker.force(true);
        } catch (java.nio.file.FileAlreadyExistsException alreadyAttempted) {
            return false;
        }
        // Linux deployment: persist the directory entry before any delivery.
        try (FileChannel directory = FileChannel.open(path.getParent(), StandardOpenOption.READ)) {
            directory.force(true);
        }
        return true;
    }

    @Override
    public void unload(DiscordIntegration dc) {
        stop();
        if (handler != null) dc.unregisterEventHandler(handler);
    }

    void stop() {
        active = false;
        if (worker != null) worker.shutdownNow();
    }
}

