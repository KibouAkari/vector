package com.kibouakari.vector;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HexFormat;
import java.util.List;
import java.util.concurrent.Flow;

public final class VectorAddonTest {
    public static void main(String[] args) throws Exception {
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

