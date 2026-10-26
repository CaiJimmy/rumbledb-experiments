package benchkit;

import java.lang.management.ManagementFactory;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Locale;

import org.rumbledb.api.Item;
import org.rumbledb.api.Rumble;

/**
 * Times a query inside one JVM: creates the Spark session and a Rumble instance once, then runs the query
 * a number of untimed warm-up iterations followed by timed iterations.
 *
 * <p>Usage (through spark-submit, with the RumbleDB jar as the application, so that RumbleDB is loaded
 * exactly as by its own command line, and this class in the same class loader through {@code --jars}):
 *
 * <pre>
 * spark-submit --class benchkit.QueryBench --jars querybench.jar rumbledb.jar QUERY WARMUPS ITERATIONS [MODE]
 * </pre>
 *
 * <p>Prints one line per phase to standard output, prefixed with {@code BENCH} and followed by a JSON object:
 * {@code setup} (creating the session and the Rumble instance), with the Java and Spark versions and the maximum
 * heap of the JVM as its result, then {@code warmup} and {@code measure} for each iteration. MODE chooses what an
 * iteration does:
 *
 * <ul>
 *   <li>{@code time} (default): {@code Rumble.runQueryToString}, which parses, compiles, evaluates and serializes
 *   the query. The line has its time and {@code allocated_bytes}, the bytes allocated by the thread that
 *   evaluates the query, i.e. the garbage that the query creates in addition to what it keeps. All benchmarks
 *   here evaluate their query locally, on that thread.
 *   <li>{@code retained}: {@code Rumble.runQuery(...).getAsList()}, which keeps the result alive. The line has
 *   {@code retained_bytes}, the heap used after a full garbage collection with the result alive minus the heap
 *   used after one before the query, i.e. the memory that the result occupies. The query must return one item,
 *   and the result reported is its {@code getSize()}, e.g. the number of entries of a map.
 * </ul>
 *
 * <p>The harness is compiled against one RumbleDB jar and runs with every benchmarked version: the methods
 * that it calls ({@code Rumble.runQueryToString(String)}, {@code Rumble.runQuery(String)},
 * {@code SequenceOfItems.getAsList()} and {@code Item.getSize()}) exist with the same signatures in all of
 * them. Only {@link #createRumble} uses reflection (see there).
 */
public final class QueryBench {
    private static final String[] SESSION_MANAGERS = {
        "org.rumbledb.spark.SparkSessionManager",
        "sparksoniq.spark.SparkSessionManager" };
    private static final com.sun.management.ThreadMXBean THREADS =
        (com.sun.management.ThreadMXBean) ManagementFactory.getThreadMXBean();

    public static void main(String[] args) throws Exception {
        if (args.length != 3 && args.length != 4) {
            System.err.println("Usage: QueryBench QUERY_FILE WARMUPS ITERATIONS [time|retained]");
            System.exit(2);
        }
        String query = Files.readString(Path.of(args[0]));
        int warmups = Integer.parseInt(args[1]);
        int iterations = Integer.parseInt(args[2]);
        boolean retained = args.length == 4 && args[3].equals("retained");

        long start = System.nanoTime();
        Object session = createSession();
        Rumble rumble = createRumble(session);
        report("setup", 0, System.nanoTime() - start, runtime(session), null);

        for (int i = 0; i < warmups + iterations; i++) {
            boolean warmup = i < warmups;
            String phase = warmup ? "warmup" : "measure";
            int iteration = warmup ? i : i - warmups;
            if (retained) {
                long before = usedHeapAfterGc();
                long t0 = System.nanoTime();
                List<Item> items = materialize(rumble, query);
                long elapsed = System.nanoTime() - t0;
                long bytes = usedHeapAfterGc() - before;
                String size = items.size() == 1 ? String.valueOf(items.get(0).getSize()) : items.size() + " items";
                report(phase, iteration, elapsed, size, "\"retained_bytes\": " + bytes);
                // Drops the result, so that it is not counted in the heap before the next iteration.
                items.clear();
            } else {
                System.gc();
                long allocated = THREADS.getCurrentThreadAllocatedBytes();
                long t0 = System.nanoTime();
                String result = rumble.runQueryToString(query);
                long elapsed = System.nanoTime() - t0;
                long bytes = THREADS.getCurrentThreadAllocatedBytes() - allocated;
                report(phase, iteration, elapsed, result.strip(), "\"allocated_bytes\": " + bytes);
            }
        }
    }

    /**
     * Creates the Spark session with RumbleDB's own session manager, with the same Spark configuration as its
     * command line. This uses reflection, because the session manager moved from {@code sparksoniq.spark} to
     * {@code org.rumbledb.spark} in August 2026, so no single name works for every version.
     */
    private static Object createSession() throws Exception {
        Class<?> manager = loadFirst(SESSION_MANAGERS);
        Object instance = manager.getMethod("getInstance").invoke(null);
        return manager.getMethod("getOrCreateSession").invoke(instance);
    }

    /**
     * Creates a Rumble instance that uses the session. This uses reflection, because the constructor takes a
     * {@code SparkSession}, and calling it directly would need Spark on the class path of the compiler.
     */
    private static Rumble createRumble(Object session) throws Exception {
        return Rumble.class.getConstructor(loadFirst("org.apache.spark.sql.SparkSession")).newInstance(session);
    }

    /** The Java and Spark versions and the maximum heap of the JVM that runs the benchmark. */
    private static String runtime(Object session) throws Exception {
        return "java " + System.getProperty("java.version") + " (" + System.getProperty("java.vendor") + ")"
            + ", spark " + session.getClass().getMethod("version").invoke(session)
            + ", max heap " + Runtime.getRuntime().maxMemory() / (1024 * 1024) + " MB";
    }

    /** Runs the query and returns its items. The sequence, which holds the runtime iterators of the query,
     * is unreachable once this method returns, so only the items are counted as retained. */
    private static List<Item> materialize(Rumble rumble, String query) {
        return rumble.runQuery(query).getAsList();
    }

    /** The heap in use after a full collection (with G1, {@code System.gc()} collects the whole heap). */
    private static long usedHeapAfterGc() {
        System.gc();
        return ManagementFactory.getMemoryMXBean().getHeapMemoryUsage().getUsed();
    }

    /** Loads the first of the classes that exists, with the class loader of RumbleDB and Spark. */
    private static Class<?> loadFirst(String... names) throws ClassNotFoundException {
        ClassLoader loader = Thread.currentThread().getContextClassLoader();
        for (String name : names) {
            try {
                return Class.forName(name, true, loader);
            } catch (ClassNotFoundException e) {
                // try the next name
            }
        }
        throw new ClassNotFoundException(String.join(" or ", names));
    }

    private static void report(String phase, int iteration, long nanos, String result, String extra) {
        StringBuilder line = new StringBuilder("BENCH {\"phase\": \"").append(phase)
            .append("\", \"iteration\": ").append(iteration)
            .append(", \"seconds\": ").append(String.format(Locale.ROOT, "%.6f", nanos / 1e9));
        if (result != null) {
            line.append(", \"result\": \"").append(escape(result)).append('"');
        }
        if (extra != null) {
            line.append(", ").append(extra);
        }
        System.out.println(line.append('}'));
        System.out.flush();
    }

    private static String escape(String s) {
        StringBuilder out = new StringBuilder();
        for (char c : s.toCharArray()) {
            switch (c) {
                case '"' -> out.append("\\\"");
                case '\\' -> out.append("\\\\");
                case '\n' -> out.append("\\n");
                case '\r' -> out.append("\\r");
                case '\t' -> out.append("\\t");
                default -> {
                    if (c < 0x20) {
                        out.append(String.format("\\u%04x", (int) c));
                    } else {
                        out.append(c);
                    }
                }
            }
        }
        return out.toString();
    }
}
