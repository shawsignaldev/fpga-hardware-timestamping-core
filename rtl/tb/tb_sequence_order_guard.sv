`timescale 1ns/1ps

module tb_sequence_order_guard;
    localparam int SEQUENCE_WIDTH = 16;
    localparam int TIMESTAMP_WIDTH = 32;

    logic clk = 1'b0;
    logic rst_n = 1'b0;
    logic valid_in = 1'b0;
    logic [SEQUENCE_WIDTH-1:0] sequence_in = '0;
    logic [TIMESTAMP_WIDTH-1:0] timestamp = '0;
    logic valid_out;
    logic duplicate;
    logic gap;
    logic out_of_order;
    logic timestamp_regression;
    logic [SEQUENCE_WIDTH-1:0] missing_count;

    sequence_order_guard #(
        .SEQUENCE_WIDTH(SEQUENCE_WIDTH),
        .TIMESTAMP_WIDTH(TIMESTAMP_WIDTH)
    ) dut (
        .clk,
        .rst_n,
        .valid_in,
        .sequence_in,
        .timestamp,
        .valid_out,
        .duplicate,
        .gap,
        .out_of_order,
        .timestamp_regression,
        .missing_count
    );

    always #5 clk = ~clk;

    task automatic send_and_expect(
        input logic [SEQUENCE_WIDTH-1:0] sequence_value,
        input logic [TIMESTAMP_WIDTH-1:0] timestamp_value,
        input logic expected_duplicate,
        input logic expected_gap,
        input logic expected_out_of_order,
        input logic expected_regression,
        input logic [SEQUENCE_WIDTH-1:0] expected_missing
    );
        @(negedge clk);
        valid_in = 1'b1;
        sequence_in = sequence_value;
        timestamp = timestamp_value;
        @(posedge clk);
        #1;
        if (!valid_out
            || duplicate !== expected_duplicate
            || gap !== expected_gap
            || out_of_order !== expected_out_of_order
            || timestamp_regression !== expected_regression
            || missing_count !== expected_missing) begin
            $fatal(1,
                "seq=%0d duplicate=%0b gap=%0b out_of_order=%0b regression=%0b missing=%0d",
                sequence_value, duplicate, gap, out_of_order, timestamp_regression, missing_count);
        end
        @(negedge clk);
        valid_in = 1'b0;
    endtask

    initial begin
        repeat (2) @(posedge clk);
        rst_n = 1'b1;

        send_and_expect(16'd10, 32'd100, 1'b0, 1'b0, 1'b0, 1'b0, 16'd0);
        send_and_expect(16'd10, 32'd101, 1'b1, 1'b0, 1'b0, 1'b0, 16'd0);
        send_and_expect(16'd13, 32'd130, 1'b0, 1'b1, 1'b0, 1'b0, 16'd2);
        send_and_expect(16'd12, 32'd120, 1'b0, 1'b0, 1'b1, 1'b1, 16'd0);
        send_and_expect(16'd14, 32'd140, 1'b0, 1'b0, 1'b0, 1'b0, 16'd0);

        @(negedge clk);
        valid_in = 1'b1;
        sequence_in = 16'd15;
        timestamp = 32'd150;
        @(posedge clk);
        #1;
        if (!valid_out || duplicate || gap || out_of_order || timestamp_regression) begin
            $fatal(1, "first back-to-back sequence failed");
        end
        @(negedge clk);
        sequence_in = 16'd17;
        timestamp = 32'd170;
        @(posedge clk);
        #1;
        if (!valid_out || duplicate || !gap || out_of_order
            || timestamp_regression || missing_count !== 16'd1) begin
            $fatal(1, "second back-to-back sequence failed");
        end

        @(negedge clk);
        rst_n = 1'b0;
        valid_in = 1'b1;
        @(posedge clk);
        #1;
        if (valid_out || duplicate || gap || out_of_order
            || timestamp_regression || missing_count !== '0) begin
            $fatal(1, "reset did not clear sequence guard outputs");
        end
        @(negedge clk);
        rst_n = 1'b1;
        valid_in = 1'b0;
        send_and_expect(16'd3, 32'd30, 1'b0, 1'b0, 1'b0, 1'b0, 16'd0);

        $display("PASS tb_sequence_order_guard");
        $finish;
    end
endmodule
