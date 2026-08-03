`timescale 1ns/1ps

module tb_timestamp_normalizer;
    localparam int TIMESTAMP_WIDTH = 32;
    localparam int DRIFT_WIDTH = 32;

    logic clk = 1'b0;
    logic rst_n = 1'b0;
    logic valid_in = 1'b0;
    logic [TIMESTAMP_WIDTH-1:0] unwrapped_timestamp = '0;
    logic signed [TIMESTAMP_WIDTH:0] offset_ns = '0;
    logic signed [DRIFT_WIDTH-1:0] drift_ppb = '0;
    logic [TIMESTAMP_WIDTH-1:0] reference_timestamp = '0;
    logic valid_out;
    logic signed [TIMESTAMP_WIDTH:0] normalized_timestamp;
    logic overflow;

    timestamp_normalizer #(
        .TIMESTAMP_WIDTH(TIMESTAMP_WIDTH),
        .DRIFT_WIDTH(DRIFT_WIDTH)
    ) dut (
        .clk,
        .rst_n,
        .valid_in,
        .unwrapped_timestamp,
        .offset_ns,
        .drift_ppb,
        .reference_timestamp,
        .valid_out,
        .normalized_timestamp,
        .overflow
    );

    always #5 clk = ~clk;

    task automatic send_and_expect(
        input logic [TIMESTAMP_WIDTH-1:0] timestamp_value,
        input logic signed [TIMESTAMP_WIDTH:0] offset_value,
        input logic signed [DRIFT_WIDTH-1:0] drift_value,
        input logic [TIMESTAMP_WIDTH-1:0] reference_value,
        input logic signed [TIMESTAMP_WIDTH:0] expected_value,
        input logic expected_overflow
    );
        @(negedge clk);
        valid_in = 1'b1;
        unwrapped_timestamp = timestamp_value;
        offset_ns = offset_value;
        drift_ppb = drift_value;
        reference_timestamp = reference_value;
        @(posedge clk);
        #1;
        if (!valid_out
            || normalized_timestamp !== expected_value
            || overflow !== expected_overflow) begin
            $fatal(1, "expected=%0d actual=%0d valid=%0b overflow=%0b",
                expected_value, normalized_timestamp, valid_out, overflow);
        end
        @(negedge clk);
        valid_in = 1'b0;
    endtask

    initial begin
        repeat (2) @(posedge clk);
        rst_n = 1'b1;

        send_and_expect(32'd1000, -33'sd25, 32'sd0, 32'd0, 33'sd1025, 1'b0);
        send_and_expect(
            32'd2000000000,
            33'sd100,
            32'sd50,
            32'd1000000000,
            33'sd1999999850,
            1'b0
        );
        send_and_expect(
            32'd2000000000,
            33'sd100,
            -32'sd50,
            32'd1000000000,
            33'sd1999999950,
            1'b0
        );
        send_and_expect(32'd0, 33'sd1, 32'sd0, 32'd0, -33'sd1, 1'b0);
        send_and_expect(32'hffffffff, 33'sd0, 32'sd0, 32'd0, 33'sd4294967295, 1'b0);
        send_and_expect(
            32'hffffffff,
            -33'sd1,
            32'sd0,
            32'd0,
            33'sd4294967295,
            1'b1
        );
        send_and_expect(32'd1, 33'sd0, -32'sd500000000, 32'd0, 33'sd1, 1'b0);

        @(negedge clk);
        rst_n = 1'b0;
        valid_in = 1'b1;
        @(posedge clk);
        #1;
        if (valid_out || overflow || normalized_timestamp !== '0) begin
            $fatal(1, "reset did not clear normalizer outputs");
        end
        @(negedge clk);
        rst_n = 1'b1;
        valid_in = 1'b0;

        $display("PASS tb_timestamp_normalizer");
        $finish;
    end
endmodule
