import org.rumbledb.api.Item;
import org.rumbledb.exceptions.ExceptionMetadata;
import org.rumbledb.items.ItemFactory;
import java.util.*;

// Builds an n-entry map the way fold-left + map:put does: one createMapItemAddingKey per entry,
// preceded by getSize(), which the type check of map:put's first argument calls.
public class MapBench {
    public static void main(String[] args) {
        boolean withSize = args[0].equals("size");
        ItemFactory f = ItemFactory.getInstance();
        for (int r = 0; r < 2; r++) build(f, 2000, withSize); // warm-up
        for (int i = 1; i < args.length; i++) {
            int n = Integer.parseInt(args[i]);
            long t0 = System.nanoTime();
            Item m = build(f, n, withSize);
            long t1 = System.nanoTime();
            System.out.printf("n=%7d  build %8.3f s  size=%d%n", n, (t1 - t0) / 1e9, m.getSize());
        }
    }
    static Item build(ItemFactory f, int n, boolean withSize) {
        Item m = f.createMapItem(new HashMap<>(), ExceptionMetadata.EMPTY_METADATA, false);
        for (int i = 1; i <= n; i++) {
            if (withSize) m.getSize();
            m = f.createMapItemAddingKey(m, f.createIntItem(i), List.of(f.createIntItem(i)));
        }
        return m;
    }
}
