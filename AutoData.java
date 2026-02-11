package org.firstinspires.ftc.teamcode.kool;
    
public class AutoData {
    
    // Path points
    public static final Point[] PATH = {
        new Point(84, 132),
        new Point(84, 120),
        new Point(84, 108),
        new Point(104, 108),
        new Point(132, 108),
        new Point(104, 120),
        new Point(84, 120)
    };
    
    // Start position
    public static final Position START_POS = new Position(
        84,
        132,
        315
    );
    
    // Functions
    public static final FunctionData[] FUNCTIONS = {
        new FunctionData(
            "score",
            84,
            120,
            315,
            FunctionType.WAIT_TILL,
            ActionType.FUNCTION
        ),
        new FunctionData(
            "intake",
            104,
            108,
            0,
            FunctionType.RUN_WHILE_MOVING,
            ActionType.FUNCTION
        ),
        new FunctionData(
            "intake",
            132,
            108,
            0,
            FunctionType.RUN_WHILE_MOVING,
            ActionType.FUNCTION
        )
    };
    
    // Templates
    public static final String[] TEMPLATES = { "intake", "outtake", "score", "park" };
    
    // Helper classes
    public static class Point {
        public final double x;
        public final double y;
        
        public Point(double x, double y) {
            this.x = x;
            this.y = y;
        }
    }
    
    public static class Position {
        public final double x;
        public final double y;
        public final double rotation;
        
        public Position(double x, double y, double rotation) {
            this.x = x;
            this.y = y;
            this.rotation = rotation;
        }
    }
    
    public static class FunctionData {
        public final String name;
        public final double x;
        public final double y;
        public final double rotation;
        public final FunctionType type;
        public final ActionType action;
        
        public FunctionData(String name, double x, double y, double rotation,
                          FunctionType type, ActionType action) {
            this.name = name;
            this.x = x;
            this.y = y;
            this.rotation = rotation;
            this.type = type;
            this.action = action;
        }
    }
    
    public enum FunctionType {
        RUN_WHILE_MOVING,
        WAIT_TILL
    }
    
    public enum ActionType {
        FUNCTION
    }
}
