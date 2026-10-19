package com.kibouakari.vector;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HexFormat;
import java.util.List;
import java.util.concurrent.Flow;

public final class VectorAddonTest {
    static void ownerWelcome() throws Exception {
        Path directory = Files.createTempDirectory("vector-owner-welcome");
        try {
            String boot = "00000000-0000-0000-0000-000000000001";
            boolean[] alive = {true};
            java.util.List<Runnable> scheduled = new java.util.ArrayList<>();
            java.util.List<String> messages = new java.util.ArrayList<>();
            VectorAddon.Bridge bridge = new VectorAddon.Bridge() {
                public void schedule(Runnable task) { scheduled.add(task); }
                public String playerName(java.util.UUID value) { throw new AssertionError("Not a player request"); }
                public void publish(String text) { messages.add(text); }
            };
            Path legacy = directory.resolve("introduction-v1.attempted"); Files.writeString(legacy, "old welcome");
            VectorAddon.OwnerWelcome welcome = new VectorAddon.OwnerWelcome(directory, boot, () -> alive[0]);
            long zero = 100;
            if (welcome.poll(bridge, zero) || !scheduled.isEmpty()) throw new AssertionError("Unarmed welcome");
            Files.writeString(welcome.request, boot + "\n");
            if (welcome.poll(bridge, zero)) throw new AssertionError("No delay");
            if (welcome.poll(bridge, zero + java.util.concurrent.TimeUnit.SECONDS.toNanos(15) - 1) || !scheduled.isEmpty())
                throw new AssertionError("Welcome before fifteen seconds");
            if (!welcome.poll(bridge, zero + java.util.concurrent.TimeUnit.SECONDS.toNanos(15)) || scheduled.size() != 1)
                throw new AssertionError("Welcome handoff absent");
            if (!messages.isEmpty() || Files.exists(welcome.marker)) throw new AssertionError("Delivery outside scheduled game task");
            scheduled.remove(0).run();
            if (messages.size() != 1 || !Files.exists(welcome.marker) || !Files.readString(legacy).equals("old welcome"))
                throw new AssertionError("Owner welcome/legacy marker changed");
            if (!welcome.poll(bridge, Long.MAX_VALUE) || !scheduled.isEmpty()) throw new AssertionError("Duplicate handoff");
            VectorAddon.OwnerWelcome reload = new VectorAddon.OwnerWelcome(directory, boot, () -> true);
            if (!reload.poll(bridge, zero)) throw new AssertionError("Attempt marker ignored");
            Files.delete(welcome.marker);
            VectorAddon.OwnerWelcome stale = new VectorAddon.OwnerWelcome(directory, "00000000-0000-0000-0000-000000000002", () -> true);
            if (!stale.poll(bridge, zero) || !scheduled.isEmpty()) throw new AssertionError("Stale boot signal replayed");
            Files.writeString(welcome.request, boot);
            VectorAddon.OwnerWelcome stopped = new VectorAddon.OwnerWelcome(directory, boot, () -> alive[0]);
            stopped.poll(bridge, zero); stopped.poll(bridge, zero + java.util.concurrent.TimeUnit.SECONDS.toNanos(15));
            alive[0] = false; scheduled.remove(0).run();
            if (Files.exists(welcome.marker) || messages.size() != 1) throw new AssertionError("Welcome after unload");
            VectorAddon generation = new VectorAddon();
            generation.start(bridge, new byte[32], legacy, false);
            VectorAddon.OwnerWelcome oldLoad = new VectorAddon.OwnerWelcome(directory, boot, generation.currentLoad());
            oldLoad.poll(bridge, zero); oldLoad.poll(bridge, zero + java.util.concurrent.TimeUnit.SECONDS.toNanos(15));
            generation.stop(); generation.start(bridge, new byte[32], legacy, false);
            scheduled.remove(0).run();
            if (Files.exists(welcome.marker) || messages.size() != 1) throw new AssertionError("Old welcome survived addon reload");
            generation.stop();
            Files.delete(welcome.request); Files.createSymbolicLink(welcome.request, legacy);
            VectorAddon.OwnerWelcome symlink = new VectorAddon.OwnerWelcome(directory, boot, () -> true);
            try { symlink.poll(bridge, zero); throw new AssertionError("Symlink request accepted"); }
            catch (java.io.IOException expected) { }
            Files.delete(welcome.request);
        } finally {
            try (var entries = Files.list(directory)) { for (Path entry : entries.toList()) Files.delete(entry); }
            Files.delete(directory);
        }
    }

    public static void main(String[] args) throws Exception {
        ownerWelcome();
        var field = VectorAddon.class.getDeclaredField("GREETING"); field.setAccessible(true);
        var greetings = (java.util.regex.Pattern) field.get(null);
        for (String greeting : List.of("Eyy", "yooo", "yo", "hello", "moin", "guten morgen", "guten nachmittag", "guten abend", "guete morge")) {
            if (!greetings.matcher(greeting + " VEcToR, synthetic question").find()) throw new AssertionError("Greeting rejected: " + greeting);
        }
        for (String ignored : List.of("ordinary chat", "heute moin Vector", "moin VectorSuffix", "guten Morgen zusammen", "eyyyyyyyyy Vector")) {
            if (greetings.matcher(ignored).find()) throw new AssertionError("Unaddressed message accepted");
        }

        if (!VectorAddon.discordName("Example Discord").equals("Example Discord")) throw new AssertionError("Discord display name changed");
        if (!VectorAddon.discordName("@<>\n").equals("DiscordUser")) throw new AssertionError("Unsafe Discord name accepted");
        var serializer = dcshadow.net.kyori.adventure.text.serializer.gson.GsonComponentSerializer.gson();
        var marked = serializer.serializeToTree(VectorAddon.presentation("Synthetic answer", true));
        String rendered = marked.toString();
        if (!rendered.contains("vector:entity/vector") || !rendered.contains("player")
                || !rendered.contains("<Vector> ") || rendered.contains("[Vector]")
                || rendered.contains("Server") || rendered.contains("clickEvent")
                || rendered.contains("click_event")) throw new AssertionError("Identity component changed");
        if (!serializer.serializeToTree(serializer.deserializeFromTree(marked)).equals(marked))
            throw new AssertionError("Installed serializer lost the logo component");
        String plain = serializer.serializeToTree(VectorAddon.presentation("Synthetic answer", false)).toString();
        if (plain.contains("texture") || !plain.contains("<Vector> "))
            throw new AssertionError("Pack-disabled fallback changed");
        if (!VectorAddon.safe("Yoo ExampleOne, Mobkills: ExampleTwo 52'000 Kills.")) throw new AssertionError();
        for (String value : List.of("/op ExampleOne", "@everyone", "https://example.invalid", "Hallo\nWelt", "gamemode creative", "\ud83d\ude00", "Text\u202eab")) {
            if (VectorAddon.safe(value)) throw new AssertionError("Unsafe output accepted");
        }
        String signature = VectorAddon.sign(HexFormat.of().parseHex("ab".repeat(32)), "1000000000", "{}".getBytes(StandardCharsets.UTF_8));
        if (!signature.equals(args[0])) throw new AssertionError("Python/Java HMAC disagreement");
        VectorAddon.LimitedBody body = new VectorAddon.LimitedBody();
        boolean[] cancelled = {false};
        body.onSubscribe(new Flow.Subscription() {
            public void request(long n) { }
            public void cancel() { cancelled[0] = true; }
        });
        body.onNext(List.of(ByteBuffer.wrap(new byte[8193])));
        if (!cancelled[0] || !body.getBody().toCompletableFuture().isCompletedExceptionally()) throw new AssertionError("Body limit absent");
        VectorAddon.LimitedBody late = new VectorAddon.LimitedBody();
        late.abort();
        boolean[] lateCancelled = {false};
        late.onSubscribe(new Flow.Subscription() {
            public void request(long n) { throw new AssertionError("Cancelled body requested data"); }
            public void cancel() { lateCancelled[0] = true; }
        });
        if (!lateCancelled[0]) throw new AssertionError("Late body subscription escaped cancellation");
        Path directory = Files.createTempDirectory("vector-introduction-test");
        try {
            Path marker = directory.resolve("intro");
            if (!VectorAddon.claimIntroduction(marker)) throw new AssertionError("First claim failed");
            if (VectorAddon.claimIntroduction(marker)) throw new AssertionError("Duplicate intro claim");
            Files.delete(marker);
        } finally { Files.delete(directory); }
        System.out.println("Addon HMAC, output policy, bounded body and durable introduction claim passed");
    }
}

